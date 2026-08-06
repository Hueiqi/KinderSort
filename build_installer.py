import os
import subprocess
import sys
import shutil
from PyInstaller.utils.hooks import collect_data_files

def build_exe():
    print("==================================================")
    print("  KinderSort Lite - Executable Packaging Tool")
    print("==================================================")

    release_dir = os.path.join(os.getcwd(), "release")
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir, exist_ok=True)

    main_script = "main.py"
    if not os.path.exists(main_script):
        print(f"[ERROR] Entrance script '{main_script}' not found!")
        return

    # 1. 自动收集 face_recognition_models 所需的 .dat 权重/模型文件
    datas = collect_data_files('face_recognition_models')
    
    # 构造 --add-data 参数
    add_data_args = []
    for src, dst in datas:
        add_data_args.extend(["--add-data", f"{src};{dst}"])

    # 2. 构造 PyInstaller 编译命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",                       # 采用文件夹模式打包
        "--windowed",                     # 隐藏控制台黑框
        "--name=KinderSortLiteSetup",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=cv2",
        "--hidden-import=face_recognition",
        "--hidden-import=face_recognition_models",
        "--hidden-import=dlib",
        "--hidden-import=sorter",
        "--hidden-import=utils",
    ] + add_data_args + [
        f"--distpath={release_dir}",
        main_script
    ]

    print("[BUILD] Running PyInstaller with face_recognition model binaries...\n")
    
    try:
        subprocess.run(cmd, check=True)
        exe_dir = os.path.join(release_dir, "KinderSortLiteSetup")
        exe_path = os.path.join(exe_dir, "KinderSortLiteSetup.exe")
        
        if os.path.exists(exe_path):
            print("\n==================================================")
            print("  🎉 SUCCESS! Executable built successfully!")
            print(f"  📂 Executable Location: {exe_path}")
            print("==================================================")
        else:
            print("\n[WARNING] Build finished but .exe file not found.")
            
    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")

if __name__ == "__main__":
    build_exe()