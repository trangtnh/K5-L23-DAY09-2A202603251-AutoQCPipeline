# Báo cáo Day 09 — Trang Ta Ngoc Huyen, 2A202603251

## 1. Kết luận trước
- **Kết luận:** **HOLD** (Mã thoát 10).
- **Số lượng ảnh:** Nhận **202 / 224 ảnh** đầu vào (loại 22 ảnh ở cửa vào intake), xuất bản nháp gồm **202 ảnh** vào `submission/export/clean_v1/`.
- **Lý do chính:** Pipeline đã loại bỏ toàn bộ 22 ảnh hỏng/trùng/rò rỉ test và tự động sửa 35 lỗi cú pháp bằng máy. Toàn bộ 6 ảnh thiếu file nhãn đã được người duyệt gán nhãn thành công, đưa số lỗi bắt buộc về 0 (`n_errors = 0`). Tuy nhiên, do ngân sách người duyệt là 80 ảnh, sau khi duyệt vẫn còn 38/202 ảnh (18.81%) chứa cảnh báo ngữ nghĩa nghi ngờ chưa được kiểm tra, vượt ngưỡng cho phép 10.00% của cổng Gate. Do đó, hệ thống quyết định **HOLD** để xuất bản nháp thử nghiệm và yêu cầu bổ sung ngân sách duyệt trước khi phát hành chính thức.

## 2. Lỗi và phân việc
Dữ liệu tổng hợp từ `02_error_list_v1.csv` (danh sách lỗi trước khi sửa):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `POSSIBLE_MISSING` | 53 | Người | Lỗi ngữ nghĩa: Model Checker phát hiện vật thể nhưng nhãn thiếu, máy không thể tự ý bịa bounding box nên chuyển người xác nhận. |
| `POSSIBLE_FALSE_POS` | 29 | Người | Lỗi ngữ nghĩa: Nhãn có box nhưng model Checker không thấy vật thể, cần mắt người xác định là vật thật hay nhãn gán thừa. |
| `POSSIBLE_LOOSE_BOX` | 28 | Người | Lỗi ngữ nghĩa: Bounding box bị lệch hoặc quá rộng so với vật thể, máy không thể đoán hình dáng thực để co giãn nên chuyển người nắn chỉnh. |
| `POSSIBLE_WRONG_CLASS` | 18 | Người | Lỗi ngữ nghĩa: Gán nhầm giữa các lớp hợp lệ (car ↔ truck ↔ bus), chỉ con người nhìn bối cảnh mới phân biệt chính xác. |
| `EMPTY_LABEL` | 12 | Người | Nhãn rỗng: Cần con người phân định đây là "ảnh nền sạch không có vật thể" hay "ảnh bị bỏ sót chưa gán nhãn". |
| `DUP_IMAGE_EXACT` | 8 | Máy | Lỗi kỹ thuật: Hai ảnh giống hệt nhau từng byte (trùng md5), máy tự động xóa an toàn ảnh trùng xuất hiện sau. |
| `BOX_OUT_OF_IMAGE` | 8 | Máy | Lỗi hình học: Box vượt khỏi toạ độ [0, 1], máy tự động cắt (clip) mép box về trong khung ảnh một cách an toàn. |
| `DUP_BOX` | 7 | Máy | Lỗi hình học: Hai box cùng lớp trùng lặp nhau (IoU > 0.9), máy tự động xóa bỏ box trùng lặp phía sau. |
| `MISSING_LABEL_FILE` | 6 | Người | Thiếu file nhãn: Lỗi bắt buộc (ERROR), máy không được tự bịa nhãn mà đánh dấu `needs_label` chuyển người gán nhãn. |
| `BAD_CLASS_ID` | 6 | Máy | Lỗi cú pháp: ID lớp ngoài phạm vi 0..3 (ví dụ ID 93, -1), máy tự động xóa dòng lỗi an toàn. |
| `BOX_TINY` | 6 | Người | Cảnh báo: Box có cạnh ngắn < 12px, cần người quyết định giữ lại theo quy định dự án hay loại bỏ do quá nhỏ. |
| `LEAK_TEST` | 5 | Máy | Vi phạm tính toàn vẹn: Ảnh trùng với tập test/val, máy bắt buộc xóa ngay ở intake để tránh rò rỉ dữ liệu đánh giá. |
| `DUP_IMAGE_NEAR` | 4 | Máy | Trùng lặp tri giác: Ảnh thu nhỏ/nén biến đổi từ ảnh trước (pHash dist <= 10), máy tự động loại bỏ. |
| `BOX_ZERO` | 4 | Máy | Lỗi cú pháp: Bounding box có chiều rộng hoặc chiều cao <= 0, máy tự động xóa dòng lỗi. |
| `CLASS_RARE` | 4 | Người | Cảnh báo thống kê: Lớp có quá ít box trong tập dữ liệu, cần người cân nhắc bổ sung mẫu hay chấp nhận mất cân bằng. |
| `BAD_SIZE` | 3 | Máy | Lỗi kích thước: Cạnh ngắn của ảnh < 250px không đủ độ phân giải, máy tự động loại bỏ ở cửa vào intake. |
| `BAD_FORMAT` | 3 | Máy | Lỗi cú pháp: Dòng nhãn thiếu cột số hoặc chứa giá trị nan/inf, máy tự động xóa dòng lỗi. |
| `BOX_HUGE` | 3 | Người | Cảnh báo: Box chiếm > 95% diện tích ảnh, cần người kiểm tra xem có phải box bao trùm nhầm hình nền không. |
| `CORRUPT_IMAGE` | 2 | Máy | Lỗi file ảnh: File ảnh bị hỏng/cắt cụt không giải mã được bằng Pillow `im.load()`, máy loại bỏ ở intake. |
| `BAD_CLASS_NAME` | 2 | Máy | Lỗi cấu hình: Tên lớp trong `data.yaml` bị viết sai chính tả/hoa thường, máy tự ghi đè chuẩn hoá lại theo cấu hình. |

**Giải thích về hàng đợi duyệt `05_review_queue.csv`:**
- Hàng đợi được sắp xếp theo điểm ưu tiên kết hợp: 6 ảnh thiếu file nhãn (`NEEDS_LABEL`) có trọng số cao nhất (weight = 10) nên được xếp ngay đầu hàng đợi (`img_0020`, `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). Đây là chiến lược bắt buộc vì thiếu nhãn là lỗi nghiêm trọng (ERROR), nếu không ưu tiên cho người gán trước thì pipeline chắc chắn sẽ dừng lại ở Rework.
- Tiếp theo là các ảnh có nhiều cảnh báo ngữ nghĩa nghiêm trọng kết hợp: `POSSIBLE_WRONG_CLASS` (weight = 3), `POSSIBLE_MISSING` (weight = 2), `POSSIBLE_FALSE_POS` (weight = 2).
- Với ngân sách 80 ảnh, người duyệt mô phỏng đã xem và xử lý được: **100% (6/6) ảnh thiếu file nhãn**, **100% (18/18) ca nghi gán sai lớp**, **94.3% (50/53) ca nghi thiếu nhãn**, cùng 12 ca thừa và 8 ca box lỏng.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 10 | P: 1.00 → 1.00<br>R: 0.50 → 0.67 (F1: 0.67 → 0.80) | Ưu tiên Precision = 1.00 tuyệt đối (tránh xoá nhầm ảnh độc lập). Tăng từ 2 lên 10 giúp bắt thêm ảnh thu nhỏ/nén (như `img_0061` thu nhỏ 85% so với `img_0186`, phash_dist = 10) mà không gây báo động giả. |
| `second_opinion.conf` | 0.25 | 0.60 | WRONG_CLASS: 0.56/0.83 → 0.62/0.83 (F1: 0.67 → 0.71)<br>MISSING: 0.50/1.00 → 0.57/1.00 (F1: 0.67 → 0.73) | Lọc bớt cảnh báo không chắc chắn của checker, tăng Precision mà vẫn giữ nguyên 100% Recall cho MISSING và 83% cho WRONG_CLASS. Tránh đẩy hàng đợi vượt quá xa ngân sách 80 ảnh, đồng thời không tăng lên >= 0.80 vì sẽ làm tụt Recall (Release giả). |

**Một chỗ calibration có thể đánh lừa bạn (kèm bằng chứng số liệu):**
- **Trên tập `data/calib/` (39 ảnh):** Khi sweep `duplicates.phash_dist`, tại ngưỡng `phash_dist = 16`, điểm F1 đạt đỉnh **0.91** (Precision = 1.00, Recall = 0.83). Nhìn vào bảng calib, ta dễ bị cám dỗ chọn ngay ngưỡng 16 để có điểm số đẹp nhất.
- **Trên tập thật `data/raw/` (224 ảnh):** Khi thử nghiệm `phash_dist = 16` trên dữ liệu thực tế, số ảnh bị gán cờ trùng lặp vọt từ 17 lên **26 ảnh**. Đáng chú ý, có đến 6 ảnh hoàn toàn độc lập (`img_0013`, `img_0017`, `img_0021`, `img_0033`, `img_0038`, `img_0115`) bị gán nhầm là `LEAK_TEST` (trùng tập test) chỉ vì ngẫu nhiên khoảng cách phash rơi vào khoảng 11–16. Hậu quả là pipeline sẽ xoá nhầm 6 ảnh sạch này khỏi tập huấn luyện!
- **Kết luận:** Tập calibration có kích thước nhỏ (39 ảnh) và phân bố lỗi nhân tạo không thể đại diện hoàn hảo cho 224 ảnh thực tế. Do đó, ta không được tối ưu mù quáng theo F1 của calib mà chọn `phash_dist = 10` để đảm bảo Precision = 1.00 trên toàn bộ dữ liệu thật.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Bằng chứng cửa chặn (Gate) hoạt động chính xác:**
- Khi chạy thử nghiệm kịch bản không có người duyệt gán nhãn:
  `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
- Kết quả: Khi ngân sách duyệt bằng 0, không có nhân viên duyệt gán nhãn cho 6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`). Ở vòng QC thứ 3, 6 lỗi bắt buộc này vẫn còn nguyên (`n_errors = 6`). Cửa chặn lập tức kích hoạt nhánh lỗi bắt buộc, đưa ra kết luận **REWORK**, tiến trình kết thúc với mã thoát **20**, và hệ thống **hoàn toàn KHÔNG xuất** dataset (thư mục `work/exp_nb/clean_v1` không hề được tạo ra). Điều này chứng minh cửa chặn thực sự bảo vệ pipeline khỏi việc phát hành dữ liệu lỗi.

**(b) Ít nhất 2 điểm mù mà pipeline không bắt được (kèm bằng chứng):**
1. **Box lỏng nhẹ (Mild loose boxes):** Với những bounding box vẽ rộng hơn vật thể nhưng độ trùng khớp IoU với dự đoán vẫn đạt từ 0.60 đến 0.85 (trên ngưỡng `iou_loose: 0.60`), model Checker coi đây là box đạt chuẩn và hoàn toàn không đưa ra cảnh báo.
2. **Điểm mù chung giữa nhãn và model lớn (Shared semantic blind spots):** Những ca phân loại khó như xe bán tải (pickup truck) hoặc xe van nhỏ mà cả nhãn thô ban đầu lẫn mô hình Checker `yolo26l` đều nhận diện nhầm thành `car` thay vì `truck`. Do cả hai cùng mắc một sai lầm ngữ nghĩa, độ bất đồng bằng 0 nên pipeline hoàn toàn bỏ sót.
3. **Ảnh trùng lặp bị biến đổi góc nhìn / crop mạnh:** Khi ảnh bị crop sâu chỉ giữ lại một góc nhỏ (< 30% diện tích) rồi lật ngang, khoảng cách pHash vượt quá ngưỡng 10 nên không thể phát hiện near-duplicate.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy do môi trường cục bộ không trang bị GPU phù hợp và thời lượng thực hiện bài lab tập trung vào phần lõi kiểm định chất lượng nhãn (QC core pipeline). Bài nộp được kiểm định và xác nhận vượt qua toàn bộ tiêu chuẩn qua `make check-core`.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối cùng:**
- Quyết định hiện tại: **HOLD** (Mã thoát 10). Dataset bản nháp đã được xuất ra `submission/export/clean_v1/`.
- Để chuyển thành **RELEASE**: Dự án cần mở rộng ngân sách duyệt của con người từ 80 ảnh lên tối thiểu 118 ảnh (tăng thêm 38 lượt duyệt cho 38 ảnh còn lại trong danh sách cảnh báo `07_error_list_v3`) để đưa tỉ lệ ảnh có cảnh báo nghi ngờ xuống dưới ngưỡng an toàn 10.00%.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** Cung cấp đầy đủ 4 ý theo chuẩn tài liệu `docs/PROMPTING.md`: định dạng đầu vào (`Dataset`, `cfg`), quy tắc kiểm định/xử lý hình học, cấu trúc trả về chuẩn hoá (`list[Issue]` hoặc `list[dict]` lưu vết thay đổi), và giới hạn an toàn (chỉ sửa bản sao trong thư mục làm việc, tuyệt đối không chỉnh sửa `data/raw`).
- **Cách kiểm tra code AI:** Chạy toàn bộ 79 bài unit test tự động trong `tests/`, đối chiếu file log thay đổi `03_fixes.csv`, và kiểm tra tính tái lập bằng cách chạy lại 2 lần kiểm chứng kết quả trùng khớp 100%.
- **Một lần AI viết sai:** Khi lập trình hàm cắt box tràn ảnh trong `pipeline/steps/autofix.py`, ban đầu AI thực hiện cắt toạ độ mà không kiểm tra trường hợp box nằm hoàn toàn ngoài khung ảnh ($x_2 < 0$), dẫn đến tạo ra box rỗng có chiều rộng âm; sau khi chạy `tests/test_autofix.py::test_box_fully_outside_is_dropped_not_negative`, lỗi đã được phát hiện và sửa lại: nếu box sau khi cắt có $w \le 0$ hoặc $h \le 0$ thì phải chuyển đổi thành hành động `drop_line`.

**(c) Thưởng CVAT (+2, tùy chọn):**
- Thao tác lọc box nhỏ trên CVAT theo `docs/CVAT_FILTER.md`: Thiết lập bộ lọc `width < 20` trên CVAT để nhanh chóng phát hiện các box nhỏ bất thường. Đối chiếu với 6 dòng `BOX_TINY` được pipeline cảnh báo: pipeline áp dụng ngưỡng khắt khe hơn theo quy tắc dự án `min_box_px: 12` (cạnh ngắn < 12px) để phát hiện box nhiễu, trong khi ngưỡng 20px của CVAT phù hợp hơn cho mắt người quan sát trên màn hình. Thuộc tính `can_review` trong CVAT được annotator sử dụng để cờ các trường hợp khó/mơ hồ (vật thể bị che khuất, thiếu sáng); trong pipeline, cơ chế tương đương chính là giá trị `priority` trong `05_review_queue.csv` được tổng hợp tự động từ mức độ bất đồng của Checker.
