#!/usr/bin/env python3
"""
Helper script to convert Tkinter/ttk widgets to CustomTkinter
This performs basic automated replacements - manual review required after!
"""

import re

def convert_to_customtkinter(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Store the file for backup
    with open(filename + '.backup', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Widget conversions
    replacements = [
        # Basic widgets
        (r'ttk\.Frame\(', 'ctk.CTkFrame('),
        (r'ttk\.Label\(', 'ctk.CTkLabel('),
        (r'ttk\.Button\(', 'ctk.CTkButton('),
        (r'ttk\.Entry\(', 'ctk.CTkEntry('),
        (r'ttk\.Checkbutton\(', 'ctk.CTkCheckBox('),
        (r'ttk\.Radiobutton\(', 'ctk.CTkRadioButton('),
        (r'ttk\.Combobox\(', 'ctk.CTkComboBox('),
        (r'ttk\.Scale\(', 'ctk.CTkSlider('),
        (r'ttk\.Scrollbar\(', 'ctk.CTkScrollbar('),
        (r'ttk\.LabelFrame\(', 'ctk.CTkFrame('),  # CTk doesn't have LabelFrame
        
        # Parameter conversions
        (r'padding=', '# padding='),  # CTk doesn't use padding parameter
        (r'foreground=', 'text_color='),
        (r'bg=', 'fg_color='),
        (r'background=', 'fg_color='),
        (r'textvariable=', 'variable='),
        (r'from_=', 'from_='),  # Same for Slider
        (r'orient=', '# orient='),  # CTk handles automatically
        (r'state="readonly"', 'state="readonly"'),  # Same for ComboBox
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write converted file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Count changes
    changes = sum(1 for a, b in zip(original, content) if a != b)
    
    print(f"Conversion complete!")
    print(f"Backup saved as: {filename}.backup")
    print(f"Made approximately {changes} character changes")
    print(f"\n⚠️  IMPORTANT:")
    print(f"1. Review the changes carefully - not all conversions are perfect")
    print(f"2. CTkTabview requires different API than ttk.Notebook")
    print(f"3. Some widgets may need manual adjustment")
    print(f"4. Test the app thoroughly")

if __name__ == "__main__":
    convert_to_customtkinter("ipixel_controller.py")
