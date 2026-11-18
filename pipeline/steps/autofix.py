"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

REMOVE_IMAGE_CODES = {
    "DUP_IMAGE_EXACT",
    "DUP_IMAGE_NEAR",
    "LEAK_TEST",
    "CORRUPT_IMAGE",
    "BAD_SIZE",
}

DROP_LINE_CODES = {
    "BAD_FORMAT",
    "BAD_CLASS_ID",
    "BOX_ZERO",
    "DUP_BOX",
}


def fix(ds, issues, cfg):
    fixes = []
    # Chỉ xử lý các lỗi có severity ERROR
    err_issues = [i for i in issues if i.severity == ERROR]
    if not err_issues:
        return fixes

    # 1. Xử lý xóa ảnh (DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE)
    removed_stems = set()
    for i in err_issues:
        if i.code in REMOVE_IMAGE_CODES or i.code.startswith("DUP_IMAGE_"):
            stem = i.image
            if stem in removed_stems:
                continue
            removed_stems.add(stem)

            img_p = ds.image_path(stem)
            before_name = img_p.name if img_p else f"{stem}.jpg"
            if img_p and img_p.exists():
                img_p.unlink()

            lbl_p = ds.label_path(stem)
            if lbl_p and lbl_p.exists():
                lbl_p.unlink()

            if stem in ds._size_cache:
                del ds._size_cache[stem]

            fixes.append({
                "image": stem,
                "line": "",
                "action": "remove_image",
                "before": before_name,
                "after": "(đã xoá)",
            })

    # 2. Xử lý đổi tên lớp trong data.yaml (BAD_CLASS_NAME)
    has_bad_class_name = any(i.code == "BAD_CLASS_NAME" for i in err_issues)
    if has_bad_class_name and ds.yaml_path.exists():
        raw_yaml = ds.yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_yaml) or {}
        old_names = str(data.get("names", {}))
        data["names"] = list(cfg["classes"])
        ds.yaml_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": old_names,
            "after": str(cfg["classes"]),
        })

    # 3. Xử lý thiếu file nhãn (MISSING_LABEL_FILE -> needs_label)
    missing_stems = set()
    for i in err_issues:
        if i.code == "MISSING_LABEL_FILE":
            stem = i.image
            if stem in removed_stems or stem in missing_stems:
                continue
            missing_stems.add(stem)
            fixes.append({
                "image": stem,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # 4. Xử lý các dòng lỗi trong file nhãn (drop_line, clip_box)
    file_line_issues = defaultdict(lambda: defaultdict(list))
    for i in err_issues:
        if i.image in removed_stems or i.line is None:
            continue
        if i.code in DROP_LINE_CODES or i.code == "BOX_OUT_OF_IMAGE":
            file_line_issues[i.image][i.line].append(i)

    for stem, lines_dict in file_line_issues.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue

        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        kept_lines = []
        file_modified = False

        for line_idx, line_text in enumerate(raw_lines, 1):
            if line_idx not in lines_dict:
                kept_lines.append(line_text)
                continue

            cur_issues = lines_dict[line_idx]
            cur_codes = {iss.code for iss in cur_issues}

            # Nếu có bất kỳ lỗi drop_line nào -> drop_line thắng
            must_drop = bool(cur_codes & DROP_LINE_CODES)

            if not must_drop and "BOX_OUT_OF_IMAGE" in cur_codes:
                try:
                    c, x, y, w, h = parse_yolo_line(line_text)
                    x1 = x - w / 2.0
                    x2 = x + w / 2.0
                    y1 = y - h / 2.0
                    y2 = y + h / 2.0

                    cx1 = max(0.0, min(1.0, x1))
                    cx2 = max(0.0, min(1.0, x2))
                    cy1 = max(0.0, min(1.0, y1))
                    cy2 = max(0.0, min(1.0, y2))

                    new_w = cx2 - cx1
                    new_h = cy2 - cy1
                    new_x = (cx1 + cx2) / 2.0
                    new_y = (cy1 + cy2) / 2.0

                    if new_w <= 0.0 or new_h <= 0.0:
                        must_drop = True
                    else:
                        clipped_line = f"{int(c)} {new_x:.6f} {new_y:.6f} {new_w:.6f} {new_h:.6f}"
                        kept_lines.append(clipped_line)
                        file_modified = True
                        fixes.append({
                            "image": stem,
                            "line": line_idx,
                            "action": "clip_box",
                            "before": line_text,
                            "after": clipped_line,
                        })
                except ValueError:
                    must_drop = True

            if must_drop:
                file_modified = True
                fixes.append({
                    "image": stem,
                    "line": line_idx,
                    "action": "drop_line",
                    "before": line_text,
                    "after": "",
                })

        if file_modified:
            new_content = "\n".join(kept_lines) + ("\n" if kept_lines else "")
            lbl_p.write_text(new_content, encoding="utf-8")

    return fixes
