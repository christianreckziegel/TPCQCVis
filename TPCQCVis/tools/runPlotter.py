import os
import subprocess
import ROOT
import glob
from array import array
import argparse
import concurrent.futures
import TPCQCVis.tools.periodPostprocessing as periodPostprocessing

# Get the environment variables
CODEDIR = os.environ['TPCQCVIS_DIR']
DATADIR = os.environ['TPCQCVIS_DATA']
REPORTDIR = os.environ['TPCQCVIS_REPORT']

# Load the ROOT macro for plotting
ROOT.gROOT.LoadMacro(f"{CODEDIR}/TPCQCVis/macro/plotQCData.C+")
ROOT.gROOT.SetBatch(True)

def addMovingWindow(path):
    file = ROOT.TFile(path,"r")
    if not file.Get("mw"): return 0
    
    with ROOT.TFile(path.split(".root")[0]+"_QC.root", "update") as outfile:
        mw_dir = file["mw"]
        tpc_dir = mw_dir["TPC"]
        for folder in tpc_dir.GetListOfKeys(): # e.g., Tracks and PID - new ROOT 6.34+ style
            outfile.cd()
            tpc_dir.Get(folder.GetName()).GetListOfKeys()
            timestamps = [timestamp.GetName() for timestamp in tpc_dir.Get(folder.GetName()).GetListOfKeys()] # new ROOT 6.34+ style
            # objects = list(set([obj.GetName() for obj in file.mw.TPC.Get(folder.GetName()).Get(timestamps[0])]))
            objects = list(dict.fromkeys(obj.GetName() for obj in tpc_dir.Get(folder.GetName()).Get(timestamps[0]))) # e.g., "h2DNClustersEta" - new ROOT 6.34+ style
            if not len(timestamps) : continue
            for item in range(len(objects)):
                outfile.cd(folder.GetName()+"QC")
                ROOT.gDirectory.mkdir(objects[item]+"_mw")
                outfile.cd(folder.GetName()+"QC/"+objects[item]+"_mw")
                for timestamp in timestamps:
                    histo = tpc_dir.Get(folder.GetName()).Get(timestamp).At(item).getObject() # new ROOT 6.34+ style
                    histo.SetName(timestamp)
                    histo.Write("")
def plot(path):
    print("Plotting run", path)
    test = ROOT.plotQCData(path)
    addMovingWindow(path)

def plot_run_param(local_dir, path, excludedPoints):
    plotter_command = f"python {CODEDIR}/TPCQCVis/tools/runPlotter.py {local_dir} --target {path} --add_run_param --excludedPoints {excludedPoints}"
    subprocess.run(plotter_command, shell=True)

def run_param_func(local_dir, run, excludedPoints):
    print("Excluded points: ", excludedPoints)
    commandRunParam = 'o2-calibration-get-run-parameters -r ' + run
    print("Running ", commandRunParam) # TODO: implement getting bfield with the macro so that this command is not needed (duration is easy to implement)
    os.system(commandRunParam)
    commandIR = f"root -l -b -q '$TPCQCVIS_DIR/TPCQCVis/macro/saveRates.C+({run}, {excludedPoints})'"
    print("Running ", commandIR)
    os.system(commandIR)
    with open('IR_avg_start_mid_end.txt') as f: 
        lines = f.readlines()
    IRavg = array('d', [float(lines[0])])
    IRstart = array('d', [float(lines[1])])
    IRmid = array('d', [float(lines[2])])
    IRend = array('d', [float(lines[3])])
    with open('Duration.txt') as f: 
        lines = f.readlines()
    Duration = array('d', [float(lines[0])])
    with open('BField.txt') as f: 
        lines = f.readlines()
    BField = array('d', [float(lines[0])])
    IRPlot_file = ROOT.TFile(f"plot_output_{run}.root", "READ")
    IRGraph = IRPlot_file.Get("RatesCanva")
    output = ROOT.TFile(local_dir + run + "_QC.root", "update")
    IRGraph.Write()
    tree = ROOT.TTree("RunParameters", "RunParameters")
    tree.Branch("IRavg", IRavg, 'IRavg/D')
    tree.Branch("IRstart", IRstart, 'IRstart/D')
    tree.Branch("IRmid", IRmid, 'IRmid/D')
    tree.Branch("IRend", IRend, 'IRend/D')
    tree.Branch("Duration", Duration, 'Duration/D')
    tree.Branch("BField", BField, 'BField/D')
    tree.Fill()
    output.Write()
    # print("ls -lt1:")
    # os.system("ls -lt")
    os.remove("IR.txt")
    os.remove("Duration.txt")
    os.remove("BField.txt")
    os.remove("DetList.txt")
    os.remove("IR_avg_start_mid_end.txt")
    os.remove("plot_output_"+run+".root")
    # print("ls -lt2:")
    # os.system("ls -lt")
    output.Close()

def main(local_dir, add_run_param, rerun, target, threads, period_postprocessing, excludedPoints):
    if target:
        if os.path.isfile(target):
            print("Plotting target run", target)
            test = ROOT.plotQCData(target)
            addMovingWindow(target)
            if add_run_param:
                run=target[-11:-5]
                print("Adding parameters for run ", run)
                run_param_func(local_dir, run, excludedPoints)
        else:
            print("Target ", target, " doesn't exist!")
    else:
        os.system("cd " + local_dir)    
        fileList = glob.glob(local_dir + "*.root")
        fileList = [file for file in fileList if ("periodOverview" not in file and "_QC" not in file)]
        runList = [file[file.rfind('/')+1:-5] for file in fileList]
        if not rerun:
            fileList_processed = glob.glob(local_dir + "*_QC.root")
            runList_processed = [file[file.rfind('/')+1:-8] for file in fileList_processed]
            if len(runList_processed) > 0:
                print(f"Not rerunning {len(runList_processed)} runs in path, use --rerun to rerun.")
            runList = [run for run in runList if run not in runList_processed]              
        print("Run list to be processed:", runList)
        
        if threads > 1:
            if add_run_param:
                with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = []
                    for run in runList:
                        path = local_dir + run + ".root"
                        if os.path.isfile(path):
                            futures.append(executor.submit(plot, path))
                for run in runList:
                    path = local_dir + run + ".root"
                    print("Adding parameters for run", run)
                    run_param_func(local_dir, run, excludedPoints)
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = []
                    for run in runList:
                        path = local_dir + run + ".root"
                        if os.path.isfile(path):
                            futures.append(executor.submit(plot, path))        
        else:
            if add_run_param:
                for run in runList:
                    path = local_dir + run + ".root"
                    if os.path.isfile(path):                            
                        print("Adding parameters for run", run)
                        plot_run_param(local_dir, path, excludedPoints)
            else:
                for run in runList:
                    path = local_dir + run + ".root"
                    if os.path.isfile(path):
                        plot(path)


        if period_postprocessing:
            print("Running period postprocessing")   
            fileListAll = glob.glob(local_dir + "*_QC.root")
            runListAll = [file[-14:-8] for file in fileListAll]             
            periodPostprocessing.main(local_dir, fileListAll, runListAll)
            


if __name__ == "__main__":
    # Get the command-line arguments
    parser = argparse.ArgumentParser(description="Script for processing data")
    parser.add_argument("local_dir", help="Path to the local directory")
    parser.add_argument(
        "--add_run_param",
        action="store_true",
        dest="add_run_param",
        default=True,
        help="Add run parameters (default: True)"
    )
    parser.add_argument(
        "--not_add_run_param",
        action="store_false",
        dest="add_run_param",
        help="Does not add run parameters (default: False)"
    )
    parser.add_argument(
        "--period_postprocessing",
        action="store_false",
        help="Add run parameters (default: True)"
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Rerun plotter for existing files (default: False)"
    )
    parser.add_argument("--target", help="Directly plot target ROOT file")
    parser.add_argument("-t", "--num_threads", type=int, default=1, help="Number of threads to be used (default: 1)")
    parser.add_argument(
        "--excludedPoints",
        type=int,
        default=10,
        dest="excludedPoints",
        help="Number of points to be excluded from the start and end of runs (in units of ~10s per point). Default: 10"
    )
    args = parser.parse_args()
    # Execute the main function
    if not args.target:
        print("Running plotter")
    main(args.local_dir, args.add_run_param, args.rerun, args.target, args.num_threads, args.period_postprocessing, args.excludedPoints)
