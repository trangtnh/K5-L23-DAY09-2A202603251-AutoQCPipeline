"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    lf_cfg = cfg["label_format"]
    overflow_tol = lf_cfg["overflow_tol"]
    dup_box_iou = lf_cfg["dup_box_iou"]
    min_box_px = lf_cfg["min_box_px"]
    max_box_frac = lf_cfg["max_box_frac"]
    num_classes = len(ds.classes)

    for lp in ds.label_files():
        stem = lp.stem
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        im_size = ds.image_size(stem)
        valid_boxes_seen = []  # list of (cls_id, cx, cy, w, h)

        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_FORMAT",
                        image=stem,
                        line=line_no,
                        message="sai định dạng dòng nhãn YOLO (cần 5 số)",
                    )
                )
                continue

            if not (0 <= cls_id < num_classes):
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_CLASS_ID",
                        image=stem,
                        line=line_no,
                        message=f"id lớp {cls_id} ngoài phạm vi 0..{num_classes - 1}",
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_ZERO",
                        image=stem,
                        line=line_no,
                        message=f"kích thước box <= 0 (w={w}, h={h})",
                    )
                )
                continue

            # Kiểm tra tràn ảnh
            left = cx - w / 2.0
            right = cx + w / 2.0
            top = cy - h / 2.0
            bottom = cy + h / 2.0
            overflow = max(0.0, -left, right - 1.0, -top, bottom - 1.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_OUT_OF_IMAGE",
                        image=stem,
                        line=line_no,
                        message=f"box tràn ra ngoài ảnh (mức tràn {overflow:.4f})",
                        extra={"overflow": float(overflow)},
                    )
                )

            # Kiểm tra trùng box (DUP_BOX) với dòng trước đó cùng lớp
            curr_box = (cx, cy, w, h)
            is_dup = False
            for prev_cls, prev_cx, prev_cy, prev_w, prev_h in valid_boxes_seen:
                if prev_cls == cls_id:
                    if iou_xywh(curr_box, (prev_cx, prev_cy, prev_w, prev_h)) > dup_box_iou:
                        is_dup = True
                        break
            if is_dup:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="DUP_BOX",
                        image=stem,
                        line=line_no,
                        message="trùng box cùng lớp với dòng trước đó",
                    )
                )

            # Lưu lại box hợp lệ cho các dòng sau so sánh DUP_BOX
            valid_boxes_seen.append((cls_id, cx, cy, w, h))

            # Kiểm tra BOX_TINY
            if im_size is not None:
                im_w, im_h = im_size
                box_w_px = w * im_w
                box_h_px = h * im_h
                if min(box_w_px, box_h_px) < min_box_px:
                    issues.append(
                        Issue(
                            check="label_format",
                            severity=WARN,
                            code="BOX_TINY",
                            image=stem,
                            line=line_no,
                            message=f"cạnh ngắn của box < {min_box_px}px",
                        )
                    )

            # Kiểm tra BOX_HUGE
            if w * h > max_box_frac:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_HUGE",
                        image=stem,
                        line=line_no,
                        message=f"diện tích box chiếm > {max_box_frac * 100:.1f}% ảnh",
                    )
                )

    return issues
