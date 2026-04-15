# JSON2MIDI
**An open-source tool for converting a chart to MIDI**

This is a Python tool built using PySide6 that allows you to convert a chart into MIDI, useful for FLP/FLM maker.

## Quick Start

### Method 1
### Run via Executable
1. Download in GitHub
2. Locate `.exe` file and Launch it
3. Click at `Browse` of `Chart File`
4. Select a chart file and open it
5. Click at `Browse` of `Metadata/Meta File` (If your chart file has detected as a V-Slice/Codename Engine format)
6. Select a `your-song.metadata.json (for V-Slice) or meta.json (for Codename Engine)` file and open it
7. Click at `Browse` of `Output MIDI`
8. Select any save location and save it
9. Set the format engine *(optional, as it is set automatically)* and difficulty *(if the format engine is V-Slice)* and BPM *(adjust according to the chart file or in the metadata/meta file)*
10. Click at `Convert to MIDI` button 
11. Wait until the process are completed.

### Method 2
### Run via Terminal
> [!NOTE]
> Use this method if you can't run the app via executable on Method 1
1. Click at `Code` button then click at `Download ZIP` button
2. Locate `.zip` file and extract it
3. Open the folder and click on `install_dependencies.bat` file
4. Wait until the process are completed then close it
5. After that right-click and click `Open in Terminal`
6. Type `venv\Scripts\activate.bat` or `venv\Scripts\activate` and enter then type `python Main.py` and enter again
7. Do steps 3-11 from Method 1. 

## Contributing
If you'd like to contribute to this open-source tool, please fork it, make your changes, and then submit a pull request.

## Bug Report
If you'd see a bug, please report the bug [here](https://github.com/sirthegamercoder/JSON2MIDI/issues)!

## License
This open-source tool is licensed under GNU Affero General Public License v3.0. See `LICENSE` for details.
