import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import threading
import queue

def parse_size(size_str):
    """将带有单位的大小字符串转换为字节数"""
    size_str = size_str.strip().lower()
    if not size_str:
        return 0

    # 正则匹配数值和单位（支持格式如 100, 100b, 100kb, 10mb, 1gb）
    match = re.match(r"^(\d+\.?\d*)\s*([kmgb]?)(b?)$", size_str)
    if not match:
        raise ValueError(f"无效的大小格式: '{size_str}'")

    number = float(match.group(1))
    unit_part = (match.group(2) + match.group(3)).rstrip('b')  # 合并单位并去除末尾的b

    # 解析单位
    if unit_part in ("", "b"):
        return int(number)
    elif unit_part in ("k", "kb"):
        return int(number * 1024)
    elif unit_part in ("m", "mb"):
        return int(number * 1024**2)
    elif unit_part in ("g", "gb"):
        return int(number * 1024**3)
    else:
        raise ValueError(f"未知的单位: '{unit_part}'")

def split_file(file_path, output_dir, chunk_sizes, log_func=print):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    original_filename = os.path.basename(file_path)

    with open(file_path, "rb") as file:
        chunk_number = 1
        for size in chunk_sizes:
            chunk_file_name = f"{original_filename}.{chunk_number:03d}"
            chunk_file_path = os.path.join(output_dir, chunk_file_name)

            with open(chunk_file_path, "wb") as chunk_file:
                remaining = size
                while remaining > 0:
                    chunk = file.read(min(remaining, 1024 * 1024))  # 每次最多读取1MB
                    if not chunk:
                        break
                    chunk_file.write(chunk)
                    remaining -= len(chunk)
            actual_size = os.path.getsize(chunk_file_path)
            log_func(f"分块 {chunk_number:03d} 已保存，目标大小：{size} 字节，实际大小：{actual_size} 字节")
            chunk_number += 1

        # 处理剩余数据（如果分块大小总和小于文件大小）
        remaining_data = file.read()
        if remaining_data:
            chunk_file_name = f"{original_filename}.{chunk_number:03d}"
            chunk_file_path = os.path.join(output_dir, chunk_file_name)
            with open(chunk_file_path, "wb") as chunk_file:
                chunk_file.write(remaining_data)
            log_func(f"剩余数据已保存到 {chunk_file_name}，大小：{len(remaining_data)} 字节")

class FileSplitterUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("文件分割工具")
        self.geometry("800x600")
        self.log_queue = queue.Queue()
        
        self.create_widgets()
        self.after(100, self.process_log_queue)
        
        # 配置网格布局
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def create_widgets(self):
        # 输入文件部分
        ttk.Label(self, text="输入文件：").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.file_entry = ttk.Entry(self, width=60)
        self.file_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self, text="浏览", command=self.browse_file).grid(row=0, column=2, padx=5, pady=5)

        # 输出目录部分
        ttk.Label(self, text="输出目录：").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_entry = ttk.Entry(self, width=60)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(self, text="浏览", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)

        # 分块大小输入
        ttk.Label(self, text="分块大小（支持单位：B, KB, MB, GB，用空格分隔）：").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.size_entry = ttk.Entry(self, width=60)
        self.size_entry.grid(row=2, column=1, padx=5, pady=5)

        # 开始按钮
        ttk.Button(self, text="开始分割", command=self.start_split).grid(row=3, column=1, pady=10)

        # 日志区域
        self.log_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=90, height=25)
        self.log_area.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

    def browse_file(self):
        filename = filedialog.askopenfilename()
        if filename:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filename)

    def browse_output(self):
        dirname = filedialog.askdirectory()
        if dirname:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, dirname)

    def log_message(self, msg):
        self.log_queue.put(msg)

    def process_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
                self.log_area.insert(tk.END, msg + "\n")
                self.log_area.see(tk.END)
            except queue.Empty:
                break
        self.after(100, self.process_log_queue)

    def start_split(self):
        input_file = self.file_entry.get()
        output_dir = self.output_entry.get()
        chunk_sizes_str = self.size_entry.get()

        # 输入验证
        if not input_file:
            messagebox.showerror("错误", "请选择输入文件")
            return
        if not os.path.exists(input_file):
            messagebox.showerror("错误", "输入文件不存在")
            return
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        try:
            # 解析分块大小
            chunk_sizes = []
            for size_str in chunk_sizes_str.split():
                if size_str.strip():
                    chunk_sizes.append(parse_size(size_str))
        except ValueError as e:
            messagebox.showerror("错误", f"分块大小格式错误：{e}")
            return

        # 自动计算分块数量（当用户只输入一个分块大小时）
        if len(chunk_sizes) == 1:
            try:
                total_size = os.path.getsize(input_file)
                chunk_size = chunk_sizes[0]
                if chunk_size <= 0:
                    raise ValueError("分块大小必须大于0")
                
                num_chunks = total_size // chunk_size
                if total_size % chunk_size != 0:
                    num_chunks += 1
                chunk_sizes = [chunk_size] * num_chunks
            except Exception as e:
                messagebox.showerror("错误", f"自动分块失败：{e}")
                return

        # 创建输出目录
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                messagebox.showerror("错误", f"无法创建输出目录：{e}")
                return

        # 启动分割线程
        def run_split():
            try:
                split_file(
                    input_file,
                    output_dir,
                    chunk_sizes,
                    log_func=self.log_message
                )
                self.log_message("文件分割完成！")
            except Exception as e:
                self.log_message(f"发生错误：{str(e)}")
                self.after(0, lambda: messagebox.showerror("错误", str(e)))

        threading.Thread(target=run_split, daemon=True).start()

if __name__ == "__main__":
    app = FileSplitterUI()
    app.mainloop()