# find_gradio.py
import gradio
import os
import sys

print("\n--- Gradio Diagnostic Tool ---")
print(f"Python Executable: {sys.executable}")
print("-" * 30)

try:
    print(f"Gradio Version Found: {gradio.__version__}")
    print(f"Gradio Package Location: {gradio.__file__}")

    gradio_dir = os.path.dirname(gradio.__file__)
    blocks_py_path = os.path.join(gradio_dir, 'blocks.py')

    print(f"Path to blocks.py: {blocks_py_path}")

    if os.path.exists(blocks_py_path):
        print("\n✅ Found blocks.py. Now checking its content...")
        with open(blocks_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # We are looking for the __init__ definition in the Blocks class
            if 'allowed_paths' in content:
                print("\n✅ SUCCESS: The 'allowed_paths' parameter was found in this file.")
                print("   This is the CORRECT version of Gradio. The error is extremely unusual.")
            else:
                print("\n❌ CRITICAL FAILURE: The 'allowed_paths' parameter is MISSING from this file.")
                print("   This is the WRONG version of Gradio, and it is the source of the error.")
    else:
        print(f"❌ CRITICAL FAILURE: Could not find blocks.py at the path: {blocks_py_path}")

except Exception as e:
    print(f"\nAn error occurred during diagnosis: {e}")

print("-" * 30)
