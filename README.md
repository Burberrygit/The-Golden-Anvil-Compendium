# Golden Anvil Compendium

The Golden Anvil Compendium is a small desktop tool that lets you browse and search through JSON price lists for tabletop RPG items. It’s designed with a modern, dark UI and gold accents to match the Golden Anvil theme.

---

## What it does

- Automatically creates a `json_files` folder the first time you run it  
- Copies in a starter `prices.json` so you have something to test right away  
- Lets you load additional `.json` price files into the `json_files` folder  
- Lets you pick which file to view from a dropdown (or merge them all together)  
- Search items by **name** or filter by a **price range**  
- Prices are automatically converted across **pp, gp, ep, sp, and cp**  
- Clean, scrollable table with sorting and a modern look

---

## How to get it

If you just want to use the program, you don’t need Python.  
Grab the latest **Windows EXE** from the [Releases page](../../releases).  

Download the `.exe`, put it wherever you like, and double-click it.  
A `json_files` folder will appear next to it, and that’s where your data lives.  

---

## Running from source

If you’d like to run the script with Python instead:

1. Make sure you have Python 3.10+ installed  
2. Install the required packages:

   
   pip install customtkinter pillow


   run: python script.py
