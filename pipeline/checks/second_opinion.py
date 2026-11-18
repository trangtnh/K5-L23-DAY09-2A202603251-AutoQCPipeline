"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg["second_opinion"]
    conf_thresh = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]

    issues = []

    for img_p in ds.image_files():
        stem = img_p.stem
        if stem not in preds:
            continue
        if not ds.label_path(stem).exists():
            continue

        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        # Lấy kích thước ảnh để tính diện tích px của prediction
        im_size = ds.image_size(stem)
        im_w, im_h = im_size if im_size is not None else (1, 1)

        # Lấy danh sách dòng nhãn hợp lệ cùng số dòng gốc
        valid_label_lines = []
        for line_no, text in raw_lines:
            try:
                c, x, y, w, h = parse_yolo_line(text)
                if 0 <= c < len(ds.classes):
                    valid_label_lines.append((line_no, c, (x, y, w, h)))
            except ValueError:
                continue

        img_preds = preds.get(stem, [])

        # P: các dự đoán có conf >= conf VÀ diện tích px >= min_area_px
        pred_issues = []
        for p in img_preds:
            p_cls, p_conf, px, py, pw, ph = p[0], p[1], p[2], p[3], p[4], p[5]
            if p_conf < conf_thresh:
                continue
            area_px = (pw * im_w) * (ph * im_h)
            if area_px < min_area_px:
                continue

            p_box = (px, py, pw, ph)

            # cands: các nhãn có IoU >= iou_missing
            cands = []
            for _, l_cls, l_box in valid_label_lines:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((l_cls, l_box, iou))

            if not cands:
                pred_issues.append(
                    Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_MISSING",
                        image=stem,
                        line=None,
                        message="model thấy vật mà nhãn không có box (nghi ngờ thiếu nhãn)",
                        extra={"conf": float(p_conf), "class": int(p_cls)},
                    )
                )
            else:
                same_cands = [c for c in cands if c[0] == p_cls]
                if same_cands:
                    best_same_iou = max(c[2] for c in same_cands)
                    if best_same_iou < iou_loose:
                        pred_issues.append(
                            Issue(
                                check="second_opinion",
                                severity=WARN,
                                code="POSSIBLE_LOOSE_BOX",
                                image=stem,
                                line=None,
                                message=f"đúng lớp nhưng box lỏng/lệch (IoU={best_same_iou:.3f} < {iou_loose})",
                                extra={"conf": float(p_conf), "iou": float(best_same_iou)},
                            )
                        )
                else:
                    diff_cands = [c for c in cands if c[0] != p_cls]
                    if diff_cands:
                        best_diff = max(diff_cands, key=lambda c: c[2])
                        best_diff_iou = best_diff[2]
                        if best_diff_iou >= iou_match:
                            pred_issues.append(
                                Issue(
                                    check="second_opinion",
                                    severity=WARN,
                                    code="POSSIBLE_WRONG_CLASS",
                                    image=stem,
                                    line=None,
                                    message=f"nghi ngờ sai lớp: nhãn={best_diff[0]} vs model={p_cls} (IoU={best_diff_iou:.3f})",
                                    extra={
                                        "conf": float(p_conf),
                                        "iou": float(best_diff_iou),
                                        "pred_class": int(p_cls),
                                        "label_class": int(best_diff[0]),
                                    },
                                )
                            )

        # Kiểm tra POSSIBLE_FALSE_POS cho từng dòng nhãn hợp lệ
        fp_preds = [p for p in img_preds if p[1] >= fp_conf]
        fp_issues = []
        for line_no, _, l_box in valid_label_lines:
            max_iou = max((iou_xywh(l_box, (p[2], p[3], p[4], p[5])) for p in fp_preds), default=0.0)
            if max_iou < iou_missing:
                fp_issues.append(
                    Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_FALSE_POS",
                        image=stem,
                        line=line_no,
                        message=f"box nhãn không khớp vật nào model thấy (max IoU={max_iou:.3f})",
                        extra={"max_iou": float(max_iou)},
                    )
                )

        issues.extend(pred_issues)
        issues.extend(fp_issues)

    return issues
