#!/usr/bin/env python3
"""
Replace known garbled Vietnamese strings in views.py with correct Vietnamese.
Creates a .bak backup before writing.
"""
from pathlib import Path

file_path = Path(__file__).resolve().parent.parent / 'inventory' / 'views.py'
if not file_path.exists():
    print('views.py not found at', file_path)
    raise SystemExit(2)

text = file_path.read_text(encoding='utf-8')

replacements = {
    "Γ£ô ─É├ú import": "Đã import",
    "Bß╗Å qua": "Bỏ qua",
    "bß║ún ghi b├ín h├áng": "bản ghi bán hàng",
    "bß║ún ghi giao dß╗ïch": "bản ghi giao dịch",
    "T├ái khoß║ún cß║ºn cß║¡p nhß║¡t kh├┤ng tß╗ôn tß║íi.": "Tài khoản cần cập nhật không tồn tại.",
    "Bß║ín kh├┤ng thß╗â tß╗▒ thay ─æß╗òi vai tr├▓ cß╗ºa t├ái khoß║ún ─æang ─æ─âng nhß║¡p.": "Bạn không thể thay đổi vai trò của tài khoản đang đăng nhập.",
    "─É├ú cß║¡p nhß║¡t vai tr├▓ cho": "Đã cập nhật vai trò cho",
    "Chß╗ë admin mß╗¢i c├│ quyß╗ün x├│a t├ái khoß║ún.": "Chỉ admin mới có quyền xóa tài khoản.",
    "T├ái khoß║ún cß║ºn x├│a kh├┤ng tß╗ôn tß║íi.": "Tài khoản cần xóa không tồn tại.",
    "Bß║ín kh├┤ng thß╗â tß╗▒ x├│a t├ái khoß║ún ─æang ─æ─âng nhß║¡p.": "Bạn không thể xóa tài khoản đang đăng nhập.",
    "Kh├┤ng thß╗â x├│a admin cuß╗æi c├╣ng cß╗ºa hß╗ç thß╗æng.": "Không thể xóa admin cuối cùng của hệ thống.",
    "Vui l├▓ng chß╗ìn file Excel hß╗úp lß╗ç.": "Vui lòng chọn file Excel hợp lệ.",
    "Dß╗» liß╗çu nhß║¡p doanh sß╗æ kh├┤ng hß╗úp lß╗ç.": "Dữ liệu nhập doanh số không hợp lệ.",
    "Dß╗» liß╗çu nhß║¡p giao dß╗ïch kh├┤ng hß╗úp lß╗ç.": "Dữ liệu nhập giao dịch không hợp lệ.",
    "Bß╗Å qua: bß║ún ghi doanh sß╗æ tr├╣ng ho├án to├án ─æ├ú tß╗ôn tß║íi.": "Bỏ qua: bản ghi doanh số trùng lặp.",
    "─É├ú th├¬m doanh sß╗æ th├ánh c├┤ng cho": "Đã thêm doanh số thành công cho",
    "Bß╗Å qua: giao dß╗ïch tr├╣ng ho├án to├án ─æ├ú tß╗ôn tß║íi.": "Bỏ qua: giao dịch trùng lặp.",
    "─É├ú th├¬m giao dß╗ïch th├ánh c├┤ng.": "Đã thêm giao dịch thành công.",
    "Dß╗» liß╗çu nhß║¡p kh├┤ng hß╗úp lß╗ç.": "Dữ liệu nhập không hợp lệ.",
    "Vui l├▓ng chß╗ìn loß║íi dß╗» liß╗çu v├á file Excel hß╗úp lß╗ç.": "Vui lòng chỉnh lỗi dữ liệu và chọn file Excel hợp lệ.",
}

for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)
        print('Replaced:', old, '->', new)

# write backup
bak = file_path.with_suffix('.py.bak')
if not bak.exists():
    bak.write_text(file_path.read_text(encoding='utf-8'), encoding='utf-8')
    print('Backup written to', bak)

file_path.write_text(text, encoding='utf-8')
print('Done writing', file_path)
