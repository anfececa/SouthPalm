import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os

def run_script():
    # Preguntar ruta del script
    script_path = filedialog.askopenfilename(
        title="Seleccionar script Python",
        filetypes=[("Python files", "*.py")]
    )
    if not script_path:
        return

    # Preguntar ruta del Excel
    excel_path = filedialog.askopenfilename(
        title="Seleccionar archivo Excel",
        filetypes=[("Excel files", "*.xlsx *.xls")]
    )
    if not excel_path:
        return

    try:
        # Ejecutar el script con el archivo como parámetro
        subprocess.run(["python", script_path, excel_path], check=True)
        messagebox.showinfo("Éxito", f"Script ejecutado:\n{os.path.basename(script_path)}\nArchivo:\n{os.path.basename(excel_path)}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Ocurrió un error al ejecutar el script:\n{e}")

root = tk.Tk()
root.title("Ejecutar Script con Excel")

btn = tk.Button(root, text="Seleccionar Script y Archivo", command=run_script)
btn.pack(padx=20, pady=20)

root.mainloop()
