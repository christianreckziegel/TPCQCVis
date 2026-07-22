import os
import subprocess
import sys
import time
from array import array
import ROOT

# Force python to flush output immediately (important for real-time logging in batch jobs)
sys.stdout.reconfigure(line_buffering=True)

# Load C++ macros once at startup
def loadMacros(dead_channel_maps=False):
    CODEDIR = os.environ['TPCQCVIS_DIR']

    # where bethe-bloch macro is located
    bb_macro = os.path.join(CODEDIR, "TPCQCVis/macro/getBetheBloch.C")
    # Use ROOT C++ macro function to retrieve Bethe-Bloch parameters
    ROOT.gROOT.ProcessLine(f'.L {bb_macro}+')

    # Only load the dead channel map macro if requested (it takes too long to fetch)
    if dead_channel_maps:
        dcm_macro = os.path.join(CODEDIR, "TPCQCVis/macro/drawDeadChannelMap.C")
        ROOT.gROOT.ProcessLine(f'.L {dcm_macro}+')

def getRunList(remote_dir):
    directories = subprocess.run(["alien_ls", remote_dir], capture_output=True)
    # Remove unnecessary characters and split the string into individual elements
    cleaned_string = directories.stdout.decode("utf-8").replace("b'", "").replace("\n", "").replace("'", "")
    elements = cleaned_string.split("/")
    runList = [element for element in elements if (element and (int(element)>100000))]
    print("Found",len(runList),"runs in", remote_dir)
    return runList

def getBetheBlochParams(runNumber):

    # # Use ROOT C++ macro function to retrieve Bethe-Bloch parameters
    from ROOT import getBetheBloch

    # Convert float array to double array
    bbParams = getBetheBloch(runNumber)
    bb_params = array('d', bbParams)

    return bbParams

def writeBetheBloch(root_file, run, bb_params):
    """Write Bethe-Bloch TTree into an already-open ROOT file."""
    bethe_bloch_tree = ROOT.TTree("BetheBlochParameters", "Tree with Bethe-Bloch fit parameters")
    branches = []
    for i in range(len(bb_params)):
        bb_param = array('d', [bb_params[i]])
        branches.append(bb_param)
        branch_name = f"BB_Parameter{i}"
        bethe_bloch_tree.Branch(branch_name, bb_param, f"{branch_name}/D")
    root_file.cd()
    bethe_bloch_tree.Fill()
    bethe_bloch_tree.Write("", ROOT.TObject.kOverwrite)

def writeDeadChannelMaps(root_file, run, binMinutes=10, maxEntries=-1):
    """Create DeadChannelMaps TDirectory and fill it via the C++ macro."""
    from ROOT import drawDeadChannelMap

    # Avoid duplicate directory if script is re-run on same file
    if root_file.GetDirectory("DeadChannelMaps"):
        print(f"  DeadChannelMaps already present for run {run}, skipping")
        return

    # Create the subdirectory inside the open ROOT file
    dcm_dir = root_file.mkdir("DeadChannelMaps")

    try:
        # Call the C++ function, passing the TDirectory* so it writes there directly
        drawDeadChannelMap(run, binMinutes, maxEntries, dcm_dir)
        print(f"  Dead channel maps written for run {run}")
    except Exception as e:
        print(f"  WARNING: Dead channel map failed for run {run}: {e}")
        # Remove the empty directory to keep the file clean
        root_file.rmdir("DeadChannelMaps")

def downloadFiles(local_dir, remote_dir, production, runList, dead_channel_maps=False):
    from TPCQCVis.src.utility import downloadAttempts

    for run in runList:
        print("Searching run",run)
        target = subprocess.run(["alien.py", "find", remote_dir + run + "/" + production + "/QC/001/", "QC.root"], capture_output=True)
        if len(target.stdout) > 0:
            target_path = target.stdout[:-1].decode('UTF-8')
            if target_path[0] == " ":
                target_path = target_path[1:]
            print("Downloading \"" + target_path+"\"")
            downloadAttempts(target_path, local_dir + run + ".root", 5)
            #subprocess.run(["alien.py", "cp", "alien:" + target_path, "file:" + local_dir + run + ".root"])

            # Open the downloaded ROOT file in update mode
            root_file = ROOT.TFile(f"{local_dir}{run}.root", "UPDATE")
            if root_file.IsZombie():
                print(f"Error opening {local_dir}{run}.root")

            # Get Bethe-Bloch parameters and write TTree
            bb_params = getBetheBlochParams(int(run))
            writeBetheBloch(root_file, run, bb_params)

            # Create DeadChannelMaps directory and fill histograms (only if flag is set)
            if dead_channel_maps:
                writeDeadChannelMaps(root_file, int(run))

            # Write and close the ROOT file
            root_file.Close()

        else:
            target = subprocess.run(["alien.py", "find", remote_dir + run + "/" + production + "/", "QC_fullrun.root"], capture_output=True)
            if len(target.stdout) > 0:
                target_path = target.stdout[:-1].decode('UTF-8')
                print("Downloading " + target_path)
                downloadAttempts(target_path, local_dir + run + ".root", 5)

                # Open ROOT file
                root_file = ROOT.TFile(f"{local_dir}{run}.root", "UPDATE")
                if root_file.IsZombie():
                    print(f"Error opening {local_dir}{run}.root")

                # Get Bethe-Bloch parameters and write TTree
                bb_params = getBetheBlochParams(int(run))
                writeBetheBloch(root_file, run, bb_params)

                # Create DeadChannelMaps directory and fill histograms (only if flag is set)
                if dead_channel_maps:
                    writeDeadChannelMaps(root_file, int(run))

                # Write and close the ROOT file
                root_file.Close()

                if False:
                    slices = subprocess.run(["alien.py", "find", remote_dir + run + "/" + production + "/", "/QC/001/QC.root"], capture_output=True)
                    slices_path = slices.stdout[:-1].decode('UTF-8').splitlines()
                    if len(slices_path) > 1:
                        print("Downloading all time slices as well.")
                        for path in slices_path:
                            timestamp = path[-(len("/QC/001/QC.root")+4):-len("/QC/001/QC.root")]
                            downloadAttempts(path, local_dir + run + "_" + timestamp +".root", 5)
                            #subprocess.run(["alien.py", "cp", "alien:" + path, "file:" + local_dir + run + "_" + timestamp +".root"])
            else:
                print("File " + remote_dir + run + "/" + production + "/QC/001/QC.root" + " not found!")
        time.sleep(1) #otherwise too many requests

# Get the command-line arguments
args = sys.argv[1:]

# Check if the correct number of arguments is provided
if len(args) < 3:
    print("Insufficient number of arguments provided.")
    print("Usage: python downloadFromAlien.py local_dir remote_dir production [runList] [--dead_channel_maps]")
    sys.exit(1)

# Assign the command-line arguments to variables
local_dir = args[0]
remote_dir = args[1]
production = args[2]

# Parse optional --dead_channel_maps flag and run list from remaining args
dead_channel_maps = "--dead-channel-maps" in args or "-dcm" in args
remaining = [a for a in args[3:] if a not in ("--dead-channel-maps", "-dcm")]
runList = remaining if remaining else None

# If runList is not provided, obtain it dynamically
if runList is None:
    runList = getRunList(remote_dir)

# Load C++ macros once at startup
# Only load the dead channel map macro if the flag is set (saves compile time)
loadMacros(dead_channel_maps)

# Download files
downloadFiles(local_dir, remote_dir, production, runList, dead_channel_maps)