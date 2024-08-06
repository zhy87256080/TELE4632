from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.app.wsgi import WSGIApplication, ControllerBase, route
import json
from webob import Response

class HotelWifiController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(HotelWifiController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.white_list = set()  # 白名单，存储允许的MAC地址
        self.account_data = {}
        self.device_traffic = {}  # 存储设备的流量使用情况
        wsgi = kwargs['wsgi']
        wsgi.register(WhitelistController, {'hotel_wifi_app': self})

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.mac_to_port[dpid][src] = in_port

        # 检查是否在白名单中
        if src in self.white_list:
            # 更新设备流量使用情况
            self.device_traffic[src] = self.device_traffic.get(src, 0) + len(msg.data)
            self.logger.info("Device %s used %d bytes", src, self.device_traffic[src])

            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
            else:
                out_port = ofproto.OFPP_FLOOD

            actions = [parser.OFPActionOutput(out_port)]

            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            if out_port != ofproto.OFPP_FLOOD:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                    return
            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                data = msg.data

            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)
        else:
            self.logger.info("MAC %s not in whitelist. Dropping packet.", src)

    def add_to_whitelist(self, mac):
        if mac not in self.white_list:
            self.white_list.add(mac)
            self.logger.info("MAC %s added to whitelist.", mac)

    def remove_from_whitelist(self, mac):
        if mac in self.white_list:
            self.white_list.remove(mac)
            self.logger.info("MAC %s removed from whitelist.", mac)

class WhitelistController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(WhitelistController, self).__init__(req, link, data, **config)
        self.hotel_wifi_app = data['hotel_wifi_app']

    @route('whitelist', '/add_to_whitelist', methods=['POST'])
    def add_to_whitelist(self, req, **kwargs):
        try:
            mac = req.json.get('mac')
            if mac:
                self.hotel_wifi_app.add_to_whitelist(mac)
                return Response(status=200, content_type='application/json')
            else:
                return Response(status=400, content_type='application/json')
        except Exception as e:
            return Response(status=500, content_type='application/json')

    @route('whitelist', '/remove_from_whitelist', methods=['POST'])
    def remove_from_whitelist(self, req, **kwargs):
        try:
            mac = req.json.get('mac')
            if mac:
                self.hotel_wifi_app.remove_from_whitelist(mac)
                return Response(status=200, content_type='application/json')
            else:
                return Response(status=400, content_type='application/json')
        except Exception as e:
            return Response(status=500, content_type='application/json')
