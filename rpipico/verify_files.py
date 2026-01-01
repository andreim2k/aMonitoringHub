import os

print("Files on Pico:")
for f in sorted(os.listdir()):
    if f.endswith('.py'):
        print(f"  {f}")

print("\nLib files:")
if os.path.exists('lib'):
    for f in sorted(os.listdir('lib')):
        print(f"  lib/{f}")
