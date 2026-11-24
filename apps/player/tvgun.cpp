#include "tvgun.hpp"
#include <charconv>
#include <sstream>
namespace dc {
Receiver::Receiver() {
    WSADATA data{};
    WSAStartup(MAKEWORD(2, 2), &data);
}
Receiver::~Receiver() {
    close();
    WSACleanup();
}
static SOCKET listenOn(int port) {
    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET)
        return s;
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<u_short>(port));
    addr.sin_addr.s_addr = INADDR_ANY;
    u_long mode = 1;
    if (bind(s, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) || ioctlsocket(s, FIONBIO, &mode)) {
        closesocket(s);
        return INVALID_SOCKET;
    }
    return s;
}
static int boundPort(SOCKET socket) {
    sockaddr_in addr{};
    int len = sizeof(addr);
    if (getsockname(socket, reinterpret_cast<sockaddr *>(&addr), &len) != 0)
        return 0;
    return ntohs(addr.sin_port);
}
int Receiver::gamePort() const { return boundPort(game); }
int Receiver::discoveryPort() const { return boundPort(discovery); }
bool Receiver::open(int g, int d) {
    close();
    game = listenOn(g);
    discovery = listenOn(d);
    if (game == INVALID_SOCKET || discovery == INVALID_SOCKET) {
        close();
        return false;
    }
    return true;
}
void Receiver::close() {
    for (SOCKET s : {game, discovery})
        if (s != INVALID_SOCKET)
            closesocket(s);
    game = discovery = INVALID_SOCKET;
    locked = false;
    peer.clear();
    token.clear();
    retired.clear();
    shots.clear();
    lastAimSeq = lastLostSeq = shotFloor = -1;
    seen = lastAim = 0;
}
void Receiver::process(std::string msg, const std::string &source, uint64_t now,
                       const RemoteHandler &deliver) {
    if (msg.empty() || msg.size() > 160)
        return;
    if (!peer.empty() && peer != source && now - seen < 2000)
        return;
    if (msg.starts_with("HELLO ")) {
        auto t = msg.substr(6);
        if (t.size() < 8 || retired.contains(t))
            return;
        if (t != token || peer != source) {
            if (!token.empty()) {
                retired.insert(token);
                if (retired.size() > 32)
                    retired.erase(retired.begin());
            }
            if (locked)
                deliver(RemoteAction::lost, {});
            peer = source;
            token = t;
            locked = false;
            shots.clear();
            lastAimSeq = lastLostSeq = shotFloor = -1;
        }
        seen = now;
        return;
    }
    if (peer.empty() || peer != source)
        return;
    seen = now;
    if (msg == "START" || msg == "COIN") {
        deliver(RemoteAction::start, {});
        return;
    }
    if (msg == "EXIT") {
        deliver(RemoteAction::exit, {});
        return;
    }
    if (msg == "RELOAD") {
        deliver(RemoteAction::reload, {});
        return;
    }
    if (msg == "SPECIAL") {
        if (locked && now - lastAim <= 600)
            deliver(RemoteAction::special, aim);
        return;
    }
    if (msg == "SHOT") {
        if (locked && now - lastAim <= 100)
            deliver(RemoteAction::shoot, aim);
        return;
    }
    auto fields = msg;
    std::replace(fields.begin(), fields.end(), ',', ' ');
    std::istringstream in(fields);
    int64_t seq;
    Point p;
    std::string op, extra;
    if (msg.starts_with("LOST,")) {
        if (!(in >> op >> seq) || in >> extra || seq <= lastAimSeq)
            return;
        lastAimSeq = lastLostSeq = seq;
        locked = false;
        deliver(RemoteAction::lost, {});
        return;
    }
    bool shot = msg.starts_with("SHOT ");
    int grade = 0;
    if (shot)
        in >> op;
    if (!(in >> p.x >> p.y) || !std::isfinite(p.x) || !std::isfinite(p.y) || (!shot && !(in >> grade)) ||
        !(in >> seq) || seq < 0 || in >> extra)
        return;
    if (shot) {
        if (!locked || now - lastAim > 600 || seq <= lastLostSeq || seq <= shotFloor ||
            shots.contains(seq))
            return;
        shots.insert(seq);
        if (shots.size() > 512) {
            shotFloor = *shots.begin();
            shots.erase(shots.begin());
        }
        deliver(RemoteAction::shoot, p);
    } else if (seq > lastAimSeq && grade >= 1 && grade <= 4) {
        lastAimSeq = seq;
        lastAim = now;
        aim = p;
        locked = true;
        deliver(RemoteAction::aim, p);
    }
}
void Receiver::poll(uint64_t now, const RemoteHandler &deliver) {
    for (SOCKET s : {game, discovery}) {
        if (s == INVALID_SOCKET)
            continue;
        for (int i = 0; i < 96; ++i) {
            sockaddr_in addr{};
            int len = sizeof(addr);
            char buf[192]{};
            int n = recvfrom(s, buf, sizeof(buf), 0, reinterpret_cast<sockaddr *>(&addr), &len);
            if (n <= 0)
                break;
            std::string msg(buf, n);
            while (!msg.empty() && (msg.back() == '\r' || msg.back() == '\n'))
                msg.pop_back();
            char host[INET_ADDRSTRLEN]{};
            inet_ntop(AF_INET, &addr.sin_addr, host, sizeof(host));
            if (s == game)
                process(msg, host, now, deliver);
            std::string answer;
            if (s == discovery && msg == "TVGUN_DISCOVER")
                answer = "TVGUN_HERE " + std::to_string(gamePort());
            if (s == game && msg.starts_with("HELLO ") && peer == host)
                answer = "FRAME 24,48";
            if (!answer.empty())
                sendto(s, answer.data(), int(answer.size()), 0, reinterpret_cast<sockaddr *>(&addr),
                       len);
        }
    }
    if (locked && now - lastAim > 600) {
        invalidate();
        deliver(RemoteAction::lost, {});
    }
}
} // namespace dc
