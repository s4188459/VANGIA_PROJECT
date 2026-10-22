"""Visible, read-only progress window for the separate recovery benchmark."""
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

DATA = Path(__file__).resolve().parent / 'data'


def main():
    window = tk.Tk()
    window.title('STT — Tiến độ chạy lại Qwen & MMS')
    window.geometry('950x460')
    window.minsize(760, 400)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Kiểm thử lại 2 model STT', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='100 mẫu/model · Chạy lần lượt · Kết quả sơ bộ cũ được giữ nguyên').pack(anchor='w', pady=(6, 20))
    status = tk.StringVar(value='Đang đọc tiến độ…')
    count = tk.StringVar()
    updated = tk.StringVar()
    detail = tk.StringVar()
    ttk.Label(frame, textvariable=status, font=('Segoe UI', 12)).pack(anchor='w')
    progress = ttk.Progressbar(frame, maximum=100)
    progress.pack(fill='x', pady=12)
    ttk.Label(frame, textvariable=count, font=('Segoe UI', 12, 'bold')).pack(anchor='w')
    table = ttk.Treeview(frame, columns=('model', 'status', 'ok', 'error'), show='headings', height=3)
    for key, title, width in [('model', 'Model', 400), ('status', 'Trạng thái', 180),
                              ('ok', 'Mẫu thành công', 125), ('error', 'Mẫu lỗi', 100)]:
        table.heading(key, text=title)
        table.column(key, width=width, anchor='w' if key == 'model' else 'center')
    table.pack(fill='x', pady=18)
    ttk.Label(frame, textvariable=updated).pack(anchor='w')
    ttk.Label(frame, textvariable=detail, wraplength=860).pack(anchor='w', pady=8)
    ttk.Label(frame, text='Tự cập nhật mỗi 2 giây. Đóng cửa sổ này không dừng benchmark. Giữ máy bật, tránh Sleep.').pack(anchor='w', side='bottom')
    labels = {'running': 'Đang chạy', 'loading': 'Đang nạp model', 'queued': 'Chờ lượt',
              'completed': 'Hoàn tất', 'completed_with_errors': 'Hoàn tất, có lỗi',
              'error': 'Lỗi', 'interrupted': 'Bị gián đoạn', 'cancelled': 'Đã hủy'}

    def refresh():
        try:
            pointer = json.loads((DATA / 'recovery-run.json').read_text('utf-8'))
            path = DATA / 'recovery' / 'runs' / pointer['run_id'] / 'run.json'
            run = json.loads(path.read_text('utf-8'))
            done, total = run['completed_tasks'], run['total_tasks']
            percent = 100 * done / total if total else 0
            progress['value'] = percent
            status.set(f"{labels.get(run['status'], run['status'])} — {run.get('message', '')}")
            count.set(f'{done}/{total} lượt đã xử lý ({percent:.1f}%)')
            table.delete(*table.get_children())
            errors = []
            for model in run['models']:
                samples = model.get('samples', [])
                ok = sum(s['status'] == 'ok' for s in samples)
                failed = sum(s['status'] == 'error' for s in samples)
                table.insert('', 'end', values=(model['config']['label'],
                    labels.get(model['status'], model['status']), ok, failed))
                if model.get('error'):
                    errors.append(str(model['error']))
            stamp = datetime.fromtimestamp(path.stat().st_mtime)
            updated.set(f"Cập nhật kết quả lúc {stamp:%H:%M:%S} · Run: {run['id']}")
            detail.set(' | '.join(errors) if errors else 'Số mẫu đã xử lý bao gồm cả mẫu lỗi; xem từng model để biết số thành công.')
        except (OSError, ValueError, KeyError) as exc:
            status.set('Chưa đọc được tiến độ; sẽ thử lại sau 2 giây.')
            detail.set(str(exc))
        window.after(2000, refresh)

    refresh()
    window.mainloop()


if __name__ == '__main__':
    main()
