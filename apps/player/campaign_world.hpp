#pragma once
#include "game.hpp"

namespace ca {
struct CampaignWorld {
    dc::fs::path root;
    std::string id;
    dc::fs::path data() const { return root / "worlds" / id; }
    dc::fs::path assets() const { return root / "assets" / id; }
    bool linyuan() const { return id == "linyuan"; }
};

inline dc::Json readCampaignJson(const dc::fs::path &file) {
    std::ifstream input(file);
    if (!input)
        throw std::runtime_error("Missing campaign data: " + file.string());
    try {
        return dc::Json::parse(input);
    } catch (const dc::Json::parse_error &e) {
        throw std::runtime_error("Invalid JSON at " + file.string() + ": " + e.what());
    }
}
} // namespace ca
