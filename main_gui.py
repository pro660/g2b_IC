import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from src.config import (
    create_folders,
    INPUT_EXCEL_PATH,
    OUTPUT_DIR
)
from src.excel_reader import read_item_numbers
from src.collector import collect_all_products
from src.excel_writer import (
    save_to_excel,
    set_output_dir,
    get_output_paths
)


class G2BCollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("나라장터 상품정보 수집기")
        self.root.geometry("760x620")
        self.root.resizable(False, False)

        self.selected_input_path = tk.StringVar()
        self.selected_output_dir = tk.StringVar(value=str(OUTPUT_DIR))

        self.progress_percent = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="[----------] 0%")
        self.progress_detail = tk.StringVar(value="현재 물품 대기 중")

        # 부드러운 진행률 애니메이션용 변수
        self.current_progress_value = 0.0
        self.target_progress_value = 0.0
        self.progress_animation_job = None

        self.is_running = False

        self.build_ui()

    def build_ui(self):
        title_label = tk.Label(
            self.root,
            text="나라장터 상품정보 수집기",
            font=("맑은 고딕", 18, "bold")
        )
        title_label.pack(pady=(18, 8))

        desc_label = tk.Label(
            self.root,
            text="input.xlsx의 물품식별번호를 기준으로 상품정보를 수집하고 result.xlsx로 저장합니다.",
            font=("맑은 고딕", 10)
        )
        desc_label.pack(pady=(0, 16))

        input_frame = tk.Frame(self.root)
        input_frame.pack(fill="x", padx=24, pady=6)

        tk.Label(
            input_frame,
            text="입력 엑셀:",
            width=12,
            anchor="w",
            font=("맑은 고딕", 10)
        ).pack(side="left")

        input_entry = tk.Entry(
            input_frame,
            textvariable=self.selected_input_path,
            font=("맑은 고딕", 10)
        )
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        input_button = tk.Button(
            input_frame,
            text="파일 선택",
            command=self.select_input_file,
            width=12
        )
        input_button.pack(side="right")

        output_frame = tk.Frame(self.root)
        output_frame.pack(fill="x", padx=24, pady=6)

        tk.Label(
            output_frame,
            text="결과 폴더:",
            width=12,
            anchor="w",
            font=("맑은 고딕", 10)
        ).pack(side="left")

        output_entry = tk.Entry(
            output_frame,
            textvariable=self.selected_output_dir,
            font=("맑은 고딕", 10)
        )
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        output_button = tk.Button(
            output_frame,
            text="폴더 선택",
            command=self.select_output_dir,
            width=12
        )
        output_button.pack(side="right")

        button_frame = tk.Frame(self.root)
        button_frame.pack(fill="x", padx=24, pady=(14, 10))

        self.start_button = tk.Button(
            button_frame,
            text="수집 시작",
            command=self.start_collecting,
            height=2,
            bg="#2f6fed",
            fg="white",
            font=("맑은 고딕", 11, "bold")
        )
        self.start_button.pack(fill="x")

        progress_title_label = tk.Label(
            self.root,
            text="현재 물품 처리 진행률",
            font=("맑은 고딕", 10, "bold"),
            anchor="w"
        )
        progress_title_label.pack(fill="x", padx=24, pady=(10, 2))

        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill="x", padx=24, pady=(2, 4))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_percent,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill="x")

        progress_text_label = tk.Label(
            self.root,
            textvariable=self.progress_text,
            font=("Consolas", 11, "bold"),
            anchor="center"
        )
        progress_text_label.pack(fill="x", padx=24, pady=(4, 0))

        progress_detail_label = tk.Label(
            self.root,
            textvariable=self.progress_detail,
            font=("맑은 고딕", 9),
            fg="#555555",
            anchor="center"
        )
        progress_detail_label.pack(fill="x", padx=24, pady=(0, 8))

        log_label = tk.Label(
            self.root,
            text="진행 로그",
            anchor="w",
            font=("맑은 고딕", 10, "bold")
        )
        log_label.pack(fill="x", padx=24, pady=(8, 4))

        self.log_box = ScrolledText(
            self.root,
            height=16,
            font=("Consolas", 9)
        )
        self.log_box.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    def select_input_file(self):
        file_path = filedialog.askopenfilename(
            title="입력 엑셀 파일 선택",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.selected_input_path.set(file_path)

    def select_output_dir(self):
        folder_path = filedialog.askdirectory(
            title="결과 저장 폴더 선택"
        )

        if folder_path:
            self.selected_output_dir.set(folder_path)

    def log(self, message):
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    def thread_safe_log(self, message):
        self.root.after(0, lambda: self.log(message))

    def make_item_progress_text(self, percent):
        """
        [###-------] 30% 형태의 물품별 진행률 텍스트를 만든다.
        """

        percent = max(0, min(100, int(percent)))

        bar_count = 10
        filled_count = int((percent / 100) * bar_count)
        empty_count = bar_count - filled_count

        bar = "#" * filled_count + "-" * empty_count

        return f"[{bar}] {percent}%"

    def update_item_progress_display(self, percent, message=""):
        """
        현재 GUI에 표시되는 진행률 값을 갱신한다.
        """

        percent = max(0, min(100, float(percent)))

        self.progress_percent.set(percent)
        self.progress_text.set(self.make_item_progress_text(percent))
        self.progress_detail.set(message)

        self.root.update_idletasks()

    def animate_progress(self):
        """
        현재 진행률이 목표 진행률까지 부드럽게 증가하도록 만든다.
        """

        difference = self.target_progress_value - self.current_progress_value

        if abs(difference) < 0.5:
            self.current_progress_value = self.target_progress_value
            self.update_item_progress_display(
                self.current_progress_value,
                self.progress_detail.get()
            )
            self.progress_animation_job = None
            return

        # 차이가 클수록 조금 더 빠르게 이동하되, 너무 딱딱하지 않게 제한
        step = max(0.4, abs(difference) * 0.08)

        if difference > 0:
            self.current_progress_value += step
            if self.current_progress_value > self.target_progress_value:
                self.current_progress_value = self.target_progress_value
        else:
            self.current_progress_value -= step
            if self.current_progress_value < self.target_progress_value:
                self.current_progress_value = self.target_progress_value

        self.update_item_progress_display(
            self.current_progress_value,
            self.progress_detail.get()
        )

        self.progress_animation_job = self.root.after(25, self.animate_progress)

    def set_item_progress_target(self, percent, message=""):
        """
        진행률 목표값을 설정한다.
        실제 화면은 animate_progress()가 부드럽게 따라간다.
        """

        percent = max(0, min(100, float(percent)))

        # 새 물품 시작처럼 목표값이 현재보다 작아지는 경우는 즉시 0으로 리셋
        if percent < self.current_progress_value:
            self.current_progress_value = percent
            self.progress_percent.set(percent)
            self.progress_text.set(self.make_item_progress_text(percent))

        self.target_progress_value = percent
        self.progress_detail.set(message)

        if self.progress_animation_job is None:
            self.progress_animation_job = self.root.after(25, self.animate_progress)

    def thread_safe_item_progress(self, percent, message=""):
        """
        수집 스레드에서 안전하게 물품별 진행률 목표값을 업데이트한다.
        """

        self.root.after(
            0,
            lambda: self.set_item_progress_target(percent, message)
        )

    def set_running_state(self, is_running):
        self.is_running = is_running

        if is_running:
            self.start_button.config(
                text="수집 중...",
                state="disabled",
                bg="#777777"
            )
        else:
            self.start_button.config(
                text="수집 시작",
                state="normal",
                bg="#2f6fed"
            )

    def validate_inputs(self):
        input_path = self.selected_input_path.get().strip()
        output_dir = self.selected_output_dir.get().strip()

        if not input_path:
            messagebox.showwarning("확인 필요", "입력 엑셀 파일을 선택하세요.")
            return False

        if not Path(input_path).exists():
            messagebox.showwarning("확인 필요", "선택한 입력 엑셀 파일이 존재하지 않습니다.")
            return False

        if not input_path.lower().endswith(".xlsx"):
            messagebox.showwarning("확인 필요", "입력 파일은 .xlsx 형식이어야 합니다.")
            return False

        if not output_dir:
            messagebox.showwarning("확인 필요", "결과 저장 폴더를 선택하세요.")
            return False

        output_path = Path(output_dir)

        if not output_path.exists():
            messagebox.showwarning("확인 필요", "선택한 결과 폴더가 존재하지 않습니다.")
            return False

        return True

    def start_collecting(self):
        if self.is_running:
            return

        if not self.validate_inputs():
            return

        self.log_box.delete("1.0", tk.END)

        self.current_progress_value = 0.0
        self.target_progress_value = 0.0
        self.progress_percent.set(0)
        self.progress_text.set("[----------] 0%")
        self.progress_detail.set("현재 물품 대기 중")

        self.set_running_state(True)

        worker = threading.Thread(
            target=self.run_collecting_worker,
            daemon=True
        )
        worker.start()

    def copy_input_to_project_data(self):
        """
        사용자가 선택한 input.xlsx를 프로젝트의 data/input.xlsx로 복사한다.
        단, 이미 같은 파일이면 복사하지 않는다.
        """

        selected_input = Path(self.selected_input_path.get().strip())

        create_folders()

        source_path = selected_input.resolve()
        target_path = INPUT_EXCEL_PATH.resolve()

        if source_path == target_path:
            self.thread_safe_log("입력 파일이 프로젝트 data/input.xlsx와 동일하여 복사를 생략합니다.")
            return

        shutil.copy2(source_path, target_path)

        self.thread_safe_log(f"입력 엑셀 복사 완료: {INPUT_EXCEL_PATH}")

    def run_collecting_worker(self):
        try:
            self.thread_safe_log("프로그램 시작")

            selected_output_dir = Path(self.selected_output_dir.get().strip())

            set_output_dir(selected_output_dir)

            output_excel_path, failed_excel_path = get_output_paths()

            self.thread_safe_log(f"결과 저장 위치: {output_excel_path}")

            self.copy_input_to_project_data()

            item_numbers = read_item_numbers()

            self.thread_safe_log(f"입력된 물품식별번호 개수: {len(item_numbers)}개")

            rows = collect_all_products(
                item_numbers,
                status_callback=self.thread_safe_log,
                item_progress_callback=self.thread_safe_item_progress,
                wait_for_enter=False
            )

            save_to_excel(rows)

            self.thread_safe_item_progress(100, "전체 작업 완료")

            self.thread_safe_log(f"최종 결과 파일: {output_excel_path}")

            if failed_excel_path.exists():
                self.thread_safe_log(f"실패 목록 파일: {failed_excel_path}")

            self.thread_safe_log("전체 작업 완료")

            self.root.after(
                0,
                lambda: messagebox.showinfo("완료", "수집이 완료되었습니다.")
            )

        except PermissionError as error:
            error_message = str(error)

            self.thread_safe_log(f"저장 오류: {error_message}")

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "저장 오류",
                    error_message
                )
            )

        except Exception as error:
            error_message = str(error)
            self.thread_safe_log(f"오류 발생: {error_message}")

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "오류 발생",
                    error_message
                )
            )

        finally:
            self.root.after(0, lambda: self.set_running_state(False))


def main():
    root = tk.Tk()
    app = G2BCollectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()