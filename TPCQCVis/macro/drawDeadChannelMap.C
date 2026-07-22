// Copyright 2019-2020 CERN and copyright holders of ALICE O2.
// See https://alice-o2.web.cern.ch/copyright for details of the copyright holders.
// All rights not expressly granted are reserved.
//
// This software is distributed under the terms of the GNU General Public
// License v3 (GPL Version 3), copied verbatim in the file "CPOYING".
//
// In applying this license CERN does not waive the privileges and immunities
// granted to it by virtue of its status as an Intergovernmental Organization
// or submit itself to any jurisdiction.

///
/// @file   drawDeadChannelMap.C
/// @author Christian Reckziegel, christian.reckziegel@cern.ch
///

// std includes
#include <iostream>
#include <vector>
#include <string>
#include <ctime>
#include <cmath>
#include <algorithm>
#include <numeric>       // std::accumulate

// ROOT includes
#include "TH1.h"
#include "TH2F.h"
#include "TCanvas.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TObjArray.h"
#include <TStopwatch.h>
#include <TROOT.h> // for gROOT
#include <TLatex.h>

// RapidJSON
#include "rapidjson/document.h"

// O2 / Framework
#include "Framework/Logger.h"
#include "CCDB/CcdbApi.h"

// O2 TPC
#include "TPCBase/DeadChannelMapCreator.h"
#include "TPCBase/Mapper.h"

using namespace o2::tpc;

// ── Time formatting helpers ───────────────────────────────────────────────────
std::string formatTime(long long ms)
{
  std::time_t t = ms / 1000;
  char buffer[64];
  std::strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", std::gmtime(&t));
  return std::string(buffer);
}

// Accept an optional output TDirectory
void drawDeadChannelMap(int run, int binMinutes = 20, int maxEntries = -1, TDirectory* outDir = nullptr) {
  // Time how much it takes to run
  TStopwatch timer;
  timer.Start();

  TH1::AddDirectory(false);
  gROOT->SetBatch(true);

  // ── 1. CCDB setup ──────────────────────────────────────────────────────────
  o2::ccdb::CcdbApi api;
  api.init("http://alice-ccdb.cern.ch");

  const std::string path = fmt::format("TPC/Calib/IDC_PadStatusMap_A/runNumber={}", run);
  auto json = api.list(path.data(), false, "application/json");

  rapidjson::Document doc;
  doc.Parse(json.data());
  if (!doc.IsObject() || !doc.HasMember("objects") || !doc["objects"].IsArray())
    throw std::runtime_error(fmt::format("Could not parse CCDB response for {}", path));

  auto entries = doc["objects"].GetArray();
  LOGP(info, "Found {} CCDB snapshots for run {}", entries.Size(), run);

  // Early exit if no snapshots found for this run
  if (entries.Size() == 0) {
    LOGP(warning, "No IDC_PadStatusMap_A snapshots found for run {}. Skipping dead channel map.", run);
    return;
  }

  // Sort by validFrom
  std::sort(entries.begin(), entries.end(), [](const auto& a, const auto& b) {
    return a["validFrom"].GetInt64() < b["validFrom"].GetInt64();
  });

  const int nEntries = (maxEntries > 0) ? std::min(maxEntries, (int)entries.Size()) : (int)entries.Size();

  // ── 2. Run time boundaries ─────────────────────────────────────────────────
  const long long tStart = entries[0]["validFrom"].GetInt64();
  const long long tEnd   = entries[nEntries - 1]["validUntil"].GetInt64();
  const double durationHr = (tEnd - tStart) / 3600000.0;

  LOGP(info, "Run start: {}", formatTime(tStart));
  LOGP(info, "Run end:   {}", formatTime(tEnd));
  LOGP(info, "Duration:  {:.2f} h", durationHr);

  // ── 3. Canvas/hour layout ─────────────────────────────────────────────────
  const int nCanvases  = std::min((int)std::ceil(durationHr), 10);
  const long long oneHour  = 3600LL * 1000LL;          // ms
  const long long binMs    = binMinutes * 60LL * 1000LL; // ms per time bin
  const int nBinsPerHour   = (int)std::ceil(3600000.0 / binMs); // e.g. 12 for 5 min

  LOGP(info, "Hourly canvases: {}, bins per hour: {} ({} min each)", nCanvases, nBinsPerHour, binMinutes);

  // ── 4. DeadChannelMapCreator ───────────────────────────────────────────────
  DeadChannelMapCreator deadChannelMapCreator;
  deadChannelMapCreator.init(api.getURL());

  const std::vector<int> pads{
    Mapper::getPadsInOROC1(),
    Mapper::getPadsInOROC2(),
    Mapper::getPadsInOROC3()
  };
  const int nStacks = 144; // 36 IROC + 36*3 OROC sub-regions

  // ── 5. Pre-load dead channel counts per snapshot per stack ─────────────────
  // Sample one snapshot every samplingMinutes to speed up fetching.
  // binMinutes is set to samplingMinutes by default (see function signature)
  // so that display resolution matches data resolution.
  double samplingMinutes = binMinutes;
  const long long samplingMs = samplingMinutes * 60LL * 1000LL; // ms
  const bool doSampling = samplingMinutes > 0;

  // Build sampled index list
  std::vector<int> sampledIndices;
  long long lastSampledTime = doSampling ? -samplingMs : LLONG_MIN;
  for (int i = 0; i < nEntries; ++i) {
    const long long t = (entries[i]["validFrom"].GetInt64() + entries[i]["validUntil"].GetInt64()) / 2;
    if (!doSampling || t - lastSampledTime >= samplingMs) {
      sampledIndices.push_back(i);
      lastSampledTime = t;
    }
  }
  const int nSampled = sampledIndices.size();
  LOGP(info, "Sampling {} out of {} snapshots (every {} min)", nSampled, nEntries, samplingMinutes);

  // deadCounts[iSampled][iStack] = number of dead channels
  std::vector<std::vector<float>> deadCounts(nSampled, std::vector<float>(nStacks, 0.f));
  std::vector<long long> snapStart(nSampled), snapEnd(nSampled);

  for (int i = 0; i < nSampled; ++i) {
    const int iEntry = sampledIndices[i];
    const auto& entry = entries[iEntry];
    snapStart[i] = entry["validFrom"].GetInt64();
    snapEnd[i]   = entry["validUntil"].GetInt64();
    const long long mid = (snapStart[i] + snapEnd[i]) / 2;

    deadChannelMapCreator.load(mid); // very time consuming CCDB data fetch
    auto& map = deadChannelMapCreator.getDeadChannelMap();

    for (size_t iRoc = 0; iRoc < map.getData().size(); ++iRoc) {
      auto& roc  = map.getCalArray(iRoc);
      auto& data = roc.getData();
      if (iRoc < 36) {
        // IROC: one stack per ROC
        deadCounts[i][iRoc] = roc.getSum<float>(); // total dead pads in this IROC
      } else {
        // OROC: split into 3 sub-stacks
        const int base = 36 + (iRoc - 36) * 3; // base stack index for this OROC
        deadCounts[i][base + 0] = std::accumulate(data.begin(), data.begin() + pads[0], 0.f);                     // OROC1 region dead pads
        deadCounts[i][base + 1] = std::accumulate(data.begin() + pads[0], data.begin() + pads[0] + pads[1], 0.f); // OROC2 region dead pads
        deadCounts[i][base + 2] = std::accumulate(data.begin() + pads[0] + pads[1], data.end(), 0.f);             // OROC3 region dead pads
      }
    }

    // Print every snapshot
    if (i % 1 == 0)
      LOGP(info, "  Loaded sampled snapshot {}/{} (entry {}/{})", i, nSampled, iEntry, nEntries);
  }

  // ── 6. Build one TH2F per hourly canvas ────────────────────────────────────
  TObjArray arrCanvases;

  for (int iHour = 0; iHour < nCanvases; ++iHour) {
    const long long hourStart = tStart + iHour * oneHour;
    const long long hourEnd   = std::min(hourStart + oneHour, tEnd);

    // Actual number of bins this hour (last hour may be shorter)
    const int nBinsThisHour = (int)std::ceil(double(hourEnd - hourStart) / double(binMs));

    auto* histogram = new TH2F(
      fmt::format("hDeadChannels_run{}_hour{}", run, iHour).data(),
      fmt::format("Dead Channels | Run {} | Hour {} ({} - {});Time bin ({} min);Stack (0-35: IROCs, 36-71: OROC1, 72-107: OROC2, 108-143: OROC3);#Dead Channels",
        run, iHour, formatTime(hourStart), formatTime(hourEnd), binMinutes).data(),
      nBinsThisHour, 0, nBinsThisHour,
      nStacks, 0, nStacks
    );
    histogram->SetStats(false);

    // Fill: loop over time bins, then snapshots, compute weighted overlap
    for (int iBin = 0; iBin < nBinsThisHour; ++iBin) {
      const long long binStart = hourStart + iBin * binMs;
      const long long binEnd   = std::min(binStart + binMs, tEnd);

      // How many snapshots fall within the current bin
      for (int iSnap = 0; iSnap < nSampled; ++iSnap) {
        // Skip snapshots that don't overlap this bin
        if (snapStart[iSnap] >= binEnd || snapEnd[iSnap] <= binStart) continue;

        const long long overlapStart = std::max(snapStart[iSnap], binStart);
        const long long overlapEnd   = std::min(snapEnd[iSnap],   binEnd);
        if (overlapStart >= overlapEnd) continue;

        // What fraction of overlaping of the snapshot fall within the time bin
        const double overlapFrac = double(overlapEnd - overlapStart) / double(snapEnd[iSnap] - snapStart[iSnap]);

        // The fraction is used for all stack
        for (int iStack = 0; iStack < nStacks; ++iStack) {
          if (deadCounts[iSnap][iStack] > 0.f) {
            histogram->Fill(iBin + 0.5, iStack + 0.5, overlapFrac * deadCounts[iSnap][iStack]);
          }
        }
      }
    }

    // Draw
    auto* canvas = new TCanvas(
      fmt::format("cHour{}_run{}", iHour, run).data(),
      fmt::format("Dead Channel Map | Run {} | Hour {}", run, iHour).data(),
      1400, 600
    );
    canvas->cd();
    histogram->Draw("COLZ");
    histogram->GetYaxis()->SetTitleY(0.55);  // Shift up
    arrCanvases.Add(canvas);

    LOGP(info, "Canvas {} done: {} - {}", iHour, formatTime(hourStart), formatTime(hourEnd));
  }

  // ── 7. Save ────────────────────────────────────────────────────────────────
  if (outDir) {
    // Write into the provided directory (e.g. inside the QC file)
    outDir->cd();
    for (int iHour = 0; iHour < arrCanvases.GetEntries(); ++iHour) {
      auto* canvas = (TCanvas*)arrCanvases.At(iHour);
      auto* histogram = (TH2F*)canvas->GetPrimitive(
        fmt::format("hDeadChannels_run{}_hour{}", run, iHour).data());
      if (histogram) histogram->Write();
      canvas->Write();
    }
    LOGP(info, "Written DeadChannelMaps into provided TDirectory");
  } else {
    // Standalone mode: write to its own ROOT file (original behavior)
    TFile* outFile = TFile::Open(
      fmt::format("DeadChannelMap_hourly_run{}.root", run).data(), "RECREATE");
    if (!outFile || outFile->IsZombie())
      throw std::runtime_error("Could not open output ROOT file");
    TDirectory* dir = outFile->mkdir("DeadChannelMaps");
    dir->cd();
    for (int iHour = 0; iHour < arrCanvases.GetEntries(); ++iHour) {
      auto* canvas = (TCanvas*)arrCanvases.At(iHour);
      auto* histogram = (TH2F*)canvas->GetPrimitive(fmt::format("hDeadChannels_run{}_hour{}", run, iHour).data());
      if (histogram) histogram->Write();
      canvas->Write();
    }
    outFile->Close();
    LOGP(info, "Done. Output: DeadChannelMap_hourly_run{}.root", run);
  }

  // Stop timing and print
  timer.Stop();
  std::cout << "Dead map channels creation took: " << timer.RealTime() / 60. << " minutes for run " << run << std::endl;
}