-- AppleScript to open Terminal and run the toolkit wrapper
set scriptPath to "/Users/nathante-aotonga/Library/Mobile Documents/com~apple~CloudDocs/NiA/Pe/pegasus_test_repo/run_switch_toolkit.sh"

tell application "Terminal"
	activate
	do script "bash -lc " & quoted form of scriptPath
end tell
