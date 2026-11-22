#pragma once
#include "game.hpp"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <functional>
#include <set>
namespace dc {
enum class RemoteAction { aim, shoot, reload, lost, start, exit };
using RemoteHandler = std::function<void(RemoteAction, Point)>;
class Receiver {
    SOCKET game = INVALID_SOCKET, discovery = INVALID_SOCKET;
    std::string peer, token;
    std::set<std::string> retired;
    std::set<int64_t> shots;
    int64_t lastAimSeq = -1, lastLostSeq = -1;
    uint64_t seen = 0, lastAim = 0;
    int64_t shotFloor = -1;
    Point aim{};
    bool locked = false;

  public:
    Receiver();
    ~Receiver();
    Receiver(const Receiver &) = delete;
    bool open(int gamePort = 9000, int discoveryPort = 8001);
    int gamePort() const;
    int discoveryPort() const;
    void close();
    void invalidate() {
        locked = false;
        lastLostSeq = lastAimSeq;
    }
    void fence() { lastLostSeq = std::max(lastLostSeq, lastAimSeq); }
    bool hasLock() const { return locked; }
    void process(std::string message, const std::string &source, uint64_t now,
                 const RemoteHandler &deliver);
    void poll(uint64_t now, const RemoteHandler &deliver);
};
} // namespace dc
