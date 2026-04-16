import ROOT
from datetime import datetime
import glob
import math

def getHistogram(file, title):
    def recursiveGetHistogram(folder, title):
        # Ensure that folder is of type TDirectory
        if not hasattr(folder, 'GetListOfKeys') or not folder.IsFolder():
            return None
        
        for item in folder.GetListOfKeys():
            # check that the item has a GetClassName() method attribute
            if hasattr(item, 'GetClassName'):
                class_name = item.GetClassName()
            else:
                class_name = 'Unknown'
            # skip TTree objects
            if class_name == "TTree":
                continue
            if item.GetName() == title:
                return folder.Get(title)
            if item.IsFolder():
                result = recursiveGetHistogram(folder.Get(item.GetName()), title)
                if result:
                    return result
        return None

    title = title.split(";")[0]
    for folder in file.GetListOfKeys():
        if folder.IsFolder():
            hist = recursiveGetHistogram(file.Get(folder.GetName()), title)
            if hist:
                return hist
    return None

def checkIfExists(files, title):
    title = title.split(";")[0] 
    objectAvailable = False
    hist = None
    if type(files) is list:
        file = files[0]
    else:
        file = files
    hist = getHistogram(file, title)
    if hist:
        return True
    else:
        print(title,"not found")
        return False

def drawMovingWindowOverlay(histograms,timestamps,normalize=False):
    ROOT.gStyle.SetPalette(55)
    palette = list(ROOT.TColor.GetPalette())
    ROOT.gStyle.SetPalette(57)
    canvas = ROOT.TCanvas("","",1000,400)
    canvas.SetGrid()
    leg = ROOT.TLegend()
    leg.SetHeader(datetime.fromtimestamp(int(timestamps[0])/1000).strftime('%d-%b-%y'))
    leg.SetNColumns(round(len(timestamps)/6))
    for i,hist in enumerate(histograms):
        if len(histograms) > 1:
            color = palette[math.floor((i/(len(histograms)-1))*(len(palette)-1))]
        else:
            color = 1
        hist.SetLineColor(color)
        hist.SetMarkerColor(color)
        if normalize and hist.Integral() != 0:
            hist.Scale(1/hist.Integral())
        hist.SetStats(0)
        hist.SetLineWidth(2)
        hist.Draw("SAME HIST")
        leg.AddEntry(hist,datetime.fromtimestamp(int(hist.GetName().split("_")[0])/1000).strftime('%H:%M'))
    return canvas,leg

def drawMovingWindow2D(histograms, timestamps):
    timestep = (int(timestamps[1])-int(timestamps[0]))/2
    my2D = ROOT.TH2F(histograms[0].GetName()+"_mw",
                     histograms[0].GetTitle() +" Moving Window",
                     len(histograms),int(timestamps[0])-timestep,int(timestamps[-1])+timestep,
                     histograms[0].GetNbinsX(),
                     histograms[0].GetXaxis().GetXmin(),
                     histograms[0].GetXaxis().GetXmax())
    for i,hist in enumerate(histograms):
        for binx in range(hist.GetNbinsX()):
            my2D.Fill(int(timestamps[i]),hist.GetBinCenter(binx+1),hist.GetBinContent(binx))
    canvas = ROOT.TCanvas()
    my2D.GetXaxis().SetTimeDisplay(1)
    my2D.GetXaxis().SetTitle("Time")
    my2D.GetYaxis().SetTitle(histograms[0].GetXaxis().GetTitle())
    my2D.Draw("COLZ")
    return my2D,canvas

def sliceAndFit(objectName,rootDataFile,fitFunc="gaus",fitRange=[40,60]):
    from copy import copy
    canvas = ROOT.TCanvas()
    legend = ROOT.TLegend()
    [hist,leg,canvo,pad1] = drawHistograms(objectName,rootDataFile,normalize=False,legend=False,
                                           pads=True,drawOption="COLZ",maxColumns=3)
    fits = []
    myFunc = ROOT.TF1("myFunc","gaus",40,60)
    canvas.cd()
    for i,histo in enumerate(hist):
        histo.FitSlicesY(myFunc)
        fit = copy(ROOT.gDirectory.Get(histo.GetName()+"_1"))
        fit.SetYTitle("Gaus Fit Mean "+ histo.GetYaxis().GetTitle())
        fit.SetXTitle(histo.GetXaxis().GetTitle())
        fit.SetTitle(quant.GetYaxis().GetTitle()+" vs. "+quant.GetXaxis().GetTitle())
        fit.SetLineWidth(2)
        fits.append(fit)
        #legend.AddEntry(fit,runList[i])
        #fit.Draw("SAME L")
    #legend.Draw()
    return fits, legend, canvas
    
def quantileProfile(hist,quantileOrder=0.5, axis="x"):
    from copy import copy
    quants = []
    for i,histo in enumerate(hist):
        if axis == "y":
            quant = copy(histo.QuantilesY(quantileOrder))
        else:
            quant = copy(histo.QuantilesX(quantileOrder))
        quant.SetYTitle("Median "+ histo.GetYaxis().GetTitle())
        quant.SetXTitle(histo.GetXaxis().GetTitle())
        quant.SetTitle(quant.GetYaxis().GetTitle()+" vs. "+quant.GetXaxis().GetTitle())
        quant.SetLineWidth(2)
        quants.append(quant)
        quants[i].SetStats(0)
    return quants

def updateRanges(histograms):
    if len(histograms)>1:
        maxRange = max([hist.GetMaximum() for hist in histograms])
        minRange = min([hist.GetMinimum() for hist in histograms])
        range = maxRange - minRange
        limMax = maxRange+range*0.1
        if minRange == 0:
            limMin = minRange
        else:
            limMin = minRange-range*0.1
        for hist in histograms:
            hist.SetMaximum(limMax)
            hist.SetMinimum(limMin)
    return limMin,limMax
        

def getPIDProfiles(qcFile,charge="pos",debug=False, rebin=1):
    assert checkIfExists(qcFile, "CdEdxPIDHypothesisVsp"), "PID hypothesis not found in QC file."
    # To compare dEdx vs p plots
    from copy import copy
    if charge == "pos":
        assert checkIfExists(qcFile, "hdEdxTotVsP_Pos_TPC"), "dEdx vs p plot not found in QC file."
        hypothesis = getHistogram(qcFile, "CdEdxPIDHypothesisVsp").GetPrimitive("CdEdxPIDHypothesisVsp_6").GetListOfPrimitives()[0]
        hist = getHistogram(qcFile, "hdEdxTotVsP_Pos_TPC")
    elif charge == "neg":
        assert checkIfExists(qcFile, "hdEdxTotVsP_Neg_TPC"), "dEdx vs p plot not found in QC file."
        hypothesis = getHistogram(qcFile, "CdEdxPIDHypothesisVsp").GetPrimitive("CdEdxPIDHypothesisVsp_1").GetListOfPrimitives()[0]
        hist = getHistogram(qcFile, "hdEdxTotVsP_Neg_TPC")
    else:
        print("Invalid charge")
        return None    
    
    if debug : print(hist.GetTitle())
    assert hist.GetNbinsX() == hypothesis.GetNbinsX(), "Same binning needed to compare."
    assert hist.GetNbinsY() == hypothesis.GetNbinsY(), "Same binning needed to compare."
    
    particleList = ["electron","muon","pion","kaon","proton","deuteron","triton"]
    nSpecies = len(particleList)
    
    selectedHists = [copy(hist) for _ in range(nSpecies)]
    for i,h in enumerate(selectedHists):
        h.Scale(0)
        h.SetName(particleList[i])
    
    dim = hypothesis.GetDimension()
    if dim < 2:
        print("Hypothesis class:", hypothesis.ClassName())
        print(f"Expected 2D histogram, got {dim}D")
        return None
        raise ValueError(f"Expected 2D histogram, got {dim}D")
        for b in range(len(hypothesis)):
            pid = hypothesis[b]
            if 0 < pid <= nSpecies:
                selectedHists[int(pid-1)].SetBinContent(b,hist[b])
    else:
        return None
        # 2D bin loop (only real fix)
        for ix in range(1, hypothesis.GetNbinsX() + 1):
            for iy in range(1, hypothesis.GetNbinsY() + 1):

                pid = int(hypothesis.GetBinContent(ix, iy))

                if 0 < pid <= nSpecies:
                    value = hist.GetBinContent(ix, iy)
                    selectedHists[pid - 1].SetBinContent(ix, iy, value)
    if rebin > 1:
        for h in selectedHists : h.RebinX(rebin)        
    profiles = [copy(selectedHist.ProfileX()) for selectedHist in selectedHists]
    return selectedHists,profiles

def downloadAttempts(target_path, local_path, nDownloadAttempts):
    import subprocess
    # Function to reliably download files from alien
    message = "ERROR"
    attempt = 0
    while ("ERROR" in message and attempt < nDownloadAttempts):
        attempt += 1
        result = subprocess.run(["alien_cp", target_path, "file:"+local_path], capture_output=True)
        message = result.stdout.decode()
        error = result.stderr.decode()
        print("\033[1mAttempt",attempt,":\033[0m")
        if error:
            print(" Error message:", error.replace('\n', ' '))
        if message:
            print(" Message:", message.replace('\n', ' '))
    if attempt == nDownloadAttempts:
        print(f"Download failed after {nDownloadAttempts} attempts. Moving on.")