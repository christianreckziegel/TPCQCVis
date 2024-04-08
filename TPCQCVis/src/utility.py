import ROOT
from datetime import datetime
import glob
import math

def getHistogram(file, title):
    title = title.split(";")[0]
    found = False
    for folder in file.GetListOfKeys():
        for item in file.Get(folder.GetName()).GetListOfKeys():
            if item.GetName() == title:
                return file.Get(folder.GetName()).Get(title)
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
        for hist in histograms:
            hist.SetMaximum(maxRange)
            hist.SetMinimum(minRange)