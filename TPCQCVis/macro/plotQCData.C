#if !defined(__CLING__) || defined(__ROOTCLING__)
#include <iostream>
#include <fmt/format.h>
#include "TFile.h"
#include "TCanvas.h"
#include <TH1.h>
#include <TH2.h>
#include <TH3.h>
#include "TLatex.h"
#include "TPCBase/Painter.h"
#include "TPCBase/CalDet.h"
#include "TPCBase/Utils.h"
#include "TPC/ClustersData.h"
#include "QualityControl/MonitorObject.h"
#include "CommonUtils/StringUtils.h"
#include "TTree.h"
#include "TKey.h"
#include "TSystem.h"
#include "TROOT.h"
#endif

/// This can read a file containing Clusters, PID and Tracks
/// QC output as stored from MC productions.
/// Call the macro with root -b -q plotQCData.C+'("filename.root")'
/// The output will be a file called filename_QC.root containing all QC plots.

// Function to draw the 2D cluster histograms with R vs Phi vs Variable
std::vector<TH1*> drawRPhi(o2::tpc::CalDet<float> calDet, std::string name)
{
  std::vector<TH1*> outVec;
  std::vector<o2::tpc::CalDet<float>> vCalDet = {calDet};
  auto h3DCalDet = o2::tpc::painter::convertCalDetToTH3(vCalDet, true, 350, 80, 255, 360, 1);
  // A-Side
  h3DCalDet.GetZaxis()->SetRangeUser(0.,1.);
  auto h2D_CalDet_Aside = h3DCalDet.Project3D("yx");
  h2D_CalDet_Aside->SetName((string("h2DRPhi")+name.c_str()+string("Aside")).c_str());
  h2D_CalDet_Aside->SetTitle((name.c_str()+string(" (A-Side)")).c_str());
  h2D_CalDet_Aside->GetYaxis()->SetTitle("R (cm)");
  h2D_CalDet_Aside->GetXaxis()->SetTitle("Phi (rad)");
  outVec.push_back(h2D_CalDet_Aside);
  // C-Side
  h3DCalDet.GetZaxis()->SetRangeUser(-1.,0.);
  auto h2D_CalDet_Cside = h3DCalDet.Project3D("yx");
  h2D_CalDet_Cside->SetName((string("h2DRPhi")+name.c_str()+string("Cside")).c_str());
  h2D_CalDet_Cside->SetTitle((name.c_str()+string(" (C-Side)")).c_str());
  h2D_CalDet_Cside->GetYaxis()->SetTitle("R (cm)");
  h2D_CalDet_Cside->GetXaxis()->SetTitle("Phi (rad)");
  outVec.push_back(h2D_CalDet_Cside);
  return outVec;
}

bool isFilled(TFile *f)
{
  // Using tracks to check if plots are filled as this task is probably always included
  TObjArray* trArr;
  if (f->GetDirectory("int")) {
    trArr = (TObjArray*)f->Get("int/TPC/PID");
  }
  else if (f->GetDirectory("TPC")) {
    trArr = (TObjArray*)f->Get("TPC/PID");
  }
  else{
    trArr = (TObjArray*)f->Get("PID");
  }
  auto trMO = (o2::quality_control::core::MonitorObject*)trArr->At(0);
  auto hist = (TH1F*)trMO->getObject();
  if (hist->GetEntries() > 0) {
    return true;
  }
  else {
    return false;
  }
}
/*
bool hasMovingWindows(TFile *f)
{
  if (f->GetDirectory("mw")) {
    TObjArray* trArr;
    trArr = (TObjArray*)f->Get("mw/TPC/Tracks");
    auto trMO = (o2::quality_control::core::MonitorObject*)trArr->At(0);
    auto hist = (TH1F*)trMO->getObject();
    if (hist->GetEntries() > 0) {
      return true;
    }
  }
  return false;
}
*/

void plotQCData(const std::string filename)
{
  /// set up I/O
  TFile *f = new TFile(filename.c_str(), "read");
  auto name = o2::utils::Str::tokenize(filename, '.');

  // Check if TPC plots are filled
  if (isFilled(f) == false) {
    std::cout << "TPC not included in run" << std::endl;
    return;
  }

  TFile *fout = new TFile(fmt::format("{}_QC.root", name[0]).data(), "recreate");
   
//-------------------------------------------------
  /// Tracks QC
  TObjArray* trArr;
  if (f->GetDirectory("int")) {
    trArr = (TObjArray*)f->Get("int/TPC/Tracks");
  }
  else if (f->GetDirectory("TPC")) {
    trArr = (TObjArray*)f->Get("TPC/Tracks");
  }
  else{
    trArr = (TObjArray*)f->Get("Tracks");
  }

  if (trArr) {
    fout->cd();
    gDirectory->mkdir("TracksQC");
    fout->cd("TracksQC");
  
    for (int i = 0; i < trArr->GetEntries(); i++) {
      auto trMO = (o2::quality_control::core::MonitorObject*)trArr->At(i);
      auto hist = (TH1F*)trMO->getObject();
      hist->Write("",TObject::kOverwrite);
    }
  }
  
//-------------------------------------------------
  /// PID QC
  TObjArray* pidArr;
  if (f->GetDirectory("int")) {
    pidArr = (TObjArray*)f->Get("int/TPC/PID");
  }
  else if (f->GetDirectory("TPC")) {
    pidArr = (TObjArray*)f->Get("TPC/PID");
  }
  else{
    pidArr = (TObjArray*)f->Get("PID");
  }

  if (pidArr) {
    fout->cd();
    gDirectory->mkdir("PIDQC");
    fout->cd("PIDQC");
  
    for (int i = 0; i < pidArr->GetEntries(); i++) {
      auto pidMO = (o2::quality_control::core::MonitorObject*)pidArr->At(i);
      auto hist = (TH1F*)pidMO->getObject();
      hist->Write("",TObject::kOverwrite);
    }
  }

//-------------------------------------------------
  /// Track Clustesters QC
  TObjArray* trackClustersArr;
  if (f->GetDirectory("int")) {
    trackClustersArr = (TObjArray*)f->Get("int/TPC/TrackClusters");
  }
  else if (f->GetDirectory("TPC")) {
    trackClustersArr = (TObjArray*)f->Get("TPC/TrackClusters");
  }
  else{
    trackClustersArr = (TObjArray*)f->Get("TrackClusters");
  }

  if (trackClustersArr) {
    fout->cd();
    gDirectory->mkdir("TrackClustersQC");
    fout->cd("TrackClustersQC");
  
    for (int i = 0; i < trackClustersArr->GetEntries(); i++) {
      auto trackClustersMO = (o2::quality_control::core::MonitorObject*)trackClustersArr->At(i);
      auto hist = (TH1F*)trackClustersMO->getObject();
      hist->Write("",TObject::kOverwrite);
    }
  }
//-------------------------------------------------

/// Cluster QC
  TObjArray* clusArr;
  if (f->GetDirectory("int")) {
    clusArr = (TObjArray*)f->Get("int/TPC/Clusters");
  }
  else if (f->GetDirectory("TPC")) {
    clusArr = (TObjArray*)f->Get("TPC/Clusters");
  }
  else{
    clusArr = (TObjArray*)f->Get("Clusters");
  }

  if (clusArr) {
    auto mo = (o2::quality_control::core::MonitorObject*)clusArr->At(0);
    auto cl = (o2::quality_control_modules::tpc::ClustersData*)mo->getObject();

    fout->cd();
    gDirectory->mkdir("ClusterQC");
    fout->cd("ClusterQC");

    // R vs Phi TH2s
    if(true) {
      auto vh2DnClusters = drawRPhi(cl->getClusters().getNClusters(),"nClusters");
      vh2DnClusters[0]->Write("",TObject::kOverwrite);
      vh2DnClusters[1]->Write("",TObject::kOverwrite);
      auto vh2DqMax = drawRPhi(cl->getClusters().getQMax(),"qMax");
      vh2DqMax[0]->Write("",TObject::kOverwrite);
      vh2DqMax[1]->Write("",TObject::kOverwrite);
      auto vh2DqTot = drawRPhi(cl->getClusters().getQTot(),"qTot");
      vh2DqTot[0]->Write("",TObject::kOverwrite);
      vh2DqTot[1]->Write("",TObject::kOverwrite);
      auto vh2DSigmaTime = drawRPhi(cl->getClusters().getSigmaTime(),"SigmaTime");
      vh2DSigmaTime[0]->Write("",TObject::kOverwrite);
      vh2DSigmaTime[1]->Write("",TObject::kOverwrite);
      auto vh2DSigmaPad = drawRPhi(cl->getClusters().getSigmaPad(),"SigmaPad");
      vh2DSigmaPad[0]->Write("",TObject::kOverwrite);
      vh2DSigmaPad[1]->Write("",TObject::kOverwrite);
      auto vh2DTimeBin = drawRPhi(cl->getClusters().getTimeBin(),"TimeBin");
      vh2DTimeBin[0]->Write("",TObject::kOverwrite);
      vh2DTimeBin[1]->Write("",TObject::kOverwrite);
    }

    // Overview Canvases
    /// ----------------------------> YOU CAN SET THE HISTO RANGES HERE!! <-----------------------------
    auto nCl = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getNClusters(), 300, 0,cl->getClusters().getNClusters().getMean()*5);       // <-----
    auto qMax = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getQMax(), 300, 0, 200);              // <-----
    auto qTot = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getQTot(), 300, 0, 600);              // <-----
    auto sigmaTime = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getSigmaTime(), 300, 0, 1.); // <-----
    auto sigmaPad = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getSigmaPad(), 300, 0, 0.8);   // <-----
    auto timeBin = o2::tpc::painter::makeSummaryCanvases(cl->getClusters().getTimeBin(), 300, 6875, 7250);  // <-----
      
    nCl[0]->Write("",TObject::kOverwrite);
    nCl[1]->Write("",TObject::kOverwrite);
    nCl[2]->Write("",TObject::kOverwrite);
    qMax[0]->Write("",TObject::kOverwrite);
    qMax[1]->Write("",TObject::kOverwrite);
    qMax[2]->Write("",TObject::kOverwrite);
    qTot[0]->Write("",TObject::kOverwrite);
    qTot[1]->Write("",TObject::kOverwrite);
    qTot[2]->Write("",TObject::kOverwrite);
    sigmaTime[0]->Write("",TObject::kOverwrite);
    sigmaTime[1]->Write("",TObject::kOverwrite);
    sigmaTime[2]->Write("",TObject::kOverwrite);
    sigmaPad[0]->Write("",TObject::kOverwrite);
    sigmaPad[1]->Write("",TObject::kOverwrite);
    sigmaPad[2]->Write("",TObject::kOverwrite);
    timeBin[0]->Write("",TObject::kOverwrite);
    timeBin[1]->Write("",TObject::kOverwrite);
    timeBin[2]->Write("",TObject::kOverwrite);
  }

  //-------------------------------------------------
  /// Moving Windows QC
  /*
  if (hasMovingWindows(f)) {
    TObjArray* mwPidArr;
    TObjArray* mwTracksArr;
    if (f->GetDirectory("mw")) {
      mwPidArr = (TObjArray*)f->Get("mw/TPC/PID");
      mwTracksArr = (TObjArray*)f->Get("mw/TPC/Tracks");
    }
    fout->cd();
    gDirectory->mkdir("mw");
    fout->cd("mw");
    if (mwPidArr) {
      gDirectory->mkdir("PIDQC");
      fout->cd("PIDQC");
      for (int i = 0; i < pidArr->GetEntries(); i++) {
        auto pidMO = (o2::quality_control::core::MonitorObject*)pidArr->At(i);
        auto hist = (TH1F*)pidMO->getObject();
        hist->Write("",TObject::kOverwrite);
      }
    }
  }
*/
//-------------------------------------------------

  // Bethe-Bloch parameters tree
  TTree* betheTree = (TTree*)f->Get("BetheBlochParameters");
  if (betheTree) {
      fout->cd();
      TTree* clonedTree = betheTree->CloneTree();
      clonedTree->Write();
  }
//-------------------------------------------------
  // Dead Channel Maps
  TDirectory* dcmDir = (TDirectory*)f->Get("DeadChannelMaps");
  if (dcmDir) {
    fout->cd();
    TDirectory* dcmDirOut = fout->mkdir("DeadChannelMaps");
    dcmDirOut->cd();
    TIter next(dcmDir->GetListOfKeys());
    TKey* key;
    while ((key = (TKey*)next())) {
      TObject* obj = key->ReadObj();
      obj->Write("", TObject::kOverwrite);
      delete obj;
    }
    std::cout << "Dead channel maps copied to QC file" << std::endl;
  }
//-------------------------------------------------
  // Time series plots (if available)
  TString tsFileName = filename;
  tsFileName.ReplaceAll(".root", "_TimeSeries.root"); // Adjust if your manual naming is different

  if (!gSystem->AccessPathName(tsFileName)) {
    std::cout << "Found TimeSeries file: " << tsFileName << std::endl;
    TFile *tsFile = TFile::Open(tsFileName, "READ");
    if (tsFile && !tsFile->IsZombie()) {
      fout->mkdir("TimeSeries");
      fout->cd("TimeSeries");
      
      TIter next(tsFile->GetListOfKeys());
      TKey *key;
      while ((key = (TKey*)next())) {
        // 1. Check if we can get the class
        const char* className = key->GetClassName();
        TClass *cl = gROOT->GetClass(className);
        if (!cl) continue; 

        // 2. Only process Canvases
        if (cl->InheritsFrom("TCanvas")) {
          TObject *obj = key->ReadObj();
          // 3. Check if object was successfully read
          if (obj) {
            obj->Write(key->GetName(), TObject::kOverwrite);
            delete obj;
          }
        }
      }
      tsFile->Close();
    }
  } else {
    std::cout << "No TimeSeries file found for " << filename << std::endl;
  }
//-------------------------------------------------
  fout->Close();
  return;
}