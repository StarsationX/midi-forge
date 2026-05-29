; Inno Setup script for midi-forge.
; Compile with: "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" midi-forge.iss

#define AppName "midi-forge"
#define AppVersion "1.1.0"
#define AppPublisher "StarsationX"
#define AppURL "https://github.com/StarsationX/midi-forge"

[Setup]
AppId={{B7F0E6E8-3A5C-4E1A-9B6E-7C8F5D2A1F00}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoDescription=midi-forge installer
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
InfoBeforeFile=
OutputDir=dist
OutputBaseFilename=midi-forge-setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#AppName} {#AppVersion}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut for Piano Extractor"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "app.py";              DestDir: "{app}"; Flags: ignoreversion
Source: "song_to_midi.py";     DestDir: "{app}"; Flags: ignoreversion
Source: "transcribe.py";       DestDir: "{app}"; Flags: ignoreversion
Source: "stem_to_midi.py";     DestDir: "{app}"; Flags: ignoreversion
Source: "yt_download.py";      DestDir: "{app}"; Flags: ignoreversion
Source: "audio_utils.py";      DestDir: "{app}"; Flags: ignoreversion
Source: "analyze.py";          DestDir: "{app}"; Flags: ignoreversion
Source: "download_assets.py";  DestDir: "{app}"; Flags: ignoreversion
Source: "verify_install.py";   DestDir: "{app}"; Flags: ignoreversion
Source: "PianoExtractor.bat";  DestDir: "{app}"; Flags: ignoreversion
Source: "SongToMidi.bat";      DestDir: "{app}"; Flags: ignoreversion
Source: "SongToMidiMax.bat";   DestDir: "{app}"; Flags: ignoreversion
Source: "Transcribe.bat";      DestDir: "{app}"; Flags: ignoreversion
Source: "StemToMidi.bat";      DestDir: "{app}"; Flags: ignoreversion
Source: "install.bat";         DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt";    DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";           DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE";             DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Piano Extractor (GUI)";  Filename: "{app}\PianoExtractor.bat"; WorkingDir: "{app}"; Comment: "Launch the midi-forge GUI"
Name: "{group}\Song to MIDI";           Filename: "{app}\SongToMidi.bat";     WorkingDir: "{app}"; Comment: "Drop a song onto this to make a MIDI"
Name: "{group}\Re-run installer";       Filename: "{app}\install.bat";        WorkingDir: "{app}"; Comment: "Re-download / repair midi-forge dependencies"
Name: "{group}\README";                 Filename: "{app}\README.md";          WorkingDir: "{app}"
Name: "{group}\GitHub page";            Filename: "{#AppURL}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Piano Extractor";  Filename: "{app}\PianoExtractor.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\install.bat"; \
  WorkingDir: "{app}"; \
  Description: "Run midi-forge installer (downloads ~3 GB of Python deps + ~700 MB model, ~10 min)"; \
  Flags: postinstall shellexec skipifsilent

[UninstallDelete]
; Wipe the venv + assets so the install folder is fully cleaned up.
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: filesandordirs; Name: "{app}\msst"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\stems"
Type: files;          Name: "{app}\*.log"

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nAfter the files are extracted, the installer will offer to download PyTorch + CUDA + the BS-Rofo model (~4 GB, ~10 min on a good connection). You'll need Python 3.10-3.13 and an NVIDIA GPU for full performance.
FinishedHeadingLabel=midi-forge is installed!
FinishedLabel=The midi-forge files are in [app].%n%nIf you ticked "Run midi-forge installer" below, it's about to start downloading Python dependencies and the model. Don't close the console window until it says "Install complete!"
