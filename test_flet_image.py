import flet as ft

try:
    img = ft.Image(
        src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        width=100,
        height=100
    )
    print("SUCCESS: Image created with data URI src")
    print(img)
except Exception as e:
    print(f"ERROR: {e}")

try:
    img2 = ft.Image(
        src_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        width=100,
        height=100
    )
    print("SUCCESS: Image created with src_base64")
except Exception as e:
    print(f"ERROR with src_base64: {e}")
