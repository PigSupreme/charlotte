#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
board.py
"""

import yaml
import networkx as nx
import matplotlib.pyplot as plt

BOARD_FILE = 'default_board.yaml'
TOKEN_FILE = 'default_tokens.yaml'
COLOR_FILE = 'default_colors.yaml'

with open(COLOR_FILE) as file:
    COLOR = yaml.load(file)

class HexBoard(object):    
    SPACE_TYPES = ['EXIT', 'FLOOR', 'LIGHT', 'PASSAGE', 'WALL']
    TOKEN_TYPES = ['GATE', 'DOOR', 'LIGHT', 'CHARACTER']

    def __init__(self):
        self.graph = nx.Graph()
        self.SPACES = dict()
        self.tokens = dict()
        self.reachable = set()
        self.revealed = set()

    def load_board(self, boardfile):
        """Static board elements/spaces only."""
        graph = nx.read_yaml(boardfile)

        # Determine board space types        
        for stype in HexBoard.SPACE_TYPES:
            self.SPACES[stype] = set()
        for node, stype in nx.get_node_attributes(graph, 'SPACE_TYPE').items():
            self.SPACES[stype].add(node)
        
        self.graph = graph
        # For drawing via networkx
        self.centers = nx.get_node_attributes(graph, 'pos')

    def load_tokens(self, tokenfile):
        """Moveable tokens with optional starting spaces."""
        tgraph = nx.read_yaml(tokenfile)
        for ttype in HexBoard.TOKEN_TYPES:
            self.tokens[ttype] = list()
        self.graph = nx.compose(self.graph, tgraph)
        
        for token, space in nx.get_node_attributes(tgraph, 'start_space').items():
            ttype = tgraph.node[token]['TOKEN_TYPE']
            self.tokens[ttype].append(token)
            if space and space in self.graph.nodes():
                self.graph.add_edge(token, space, token=ttype)
            else:
                print('Warning: Cannot place %s on space %s.' % (token,space))

    def place_token(self, node, token):
        # Check that node is a valid space
        # Check that token type is valid for the type of space
        # Put an edge between token and node; annotate edge somehow...
        pass
    
    def remove_token(self, token):
        # Check that token is on the board
        # Remove edge, etc.
        pass

    def compute_exits(self):
        """Exits are OPEN unless a closed GATE token is present."""
        self.closed_exits = set()
        for token in self.tokens['GATE']:
            for space in self.graph.neighbors(token):
                if self.graph.nodes[space]['SPACE_TYPE'] != 'EXIT':
                    raise Exception('Gate token on non-exit space')
                self.centers[token] = self.centers[space]
                if self.graph.node[token]['closed']:
                    self.closed_exits.add(space)
        self.open_exits = set(self.SPACES['EXIT']) - self.closed_exits

    def compute_passages(self):
        """Passages are OPEN unless a closed DOOR token is present."""
        self.closed_passages = set()
        for token in self.tokens['DOOR']:
            for space in self.graph.neighbors(token):
                if self.graph.nodes[space]['SPACE_TYPE'] != 'PASSAGE':
                    raise Exception('Door token on non-passage space')
                self.centers[token] = self.centers[space]
                if self.graph.node[token]['closed']:
                    self.closed_passages.add(space)
        self.open_passages = set(self.SPACES['PASSAGE']) - self.closed_passages
        
        self.passage_graph = nx.complete_graph(self.open_passages)
        self.passage_graph.add_nodes_from(self.closed_passages)
        
    def update_reachable(self, *, with_exits=False, with_passages=False, with_walls=False):
        nodes = self.SPACES['FLOOR'].union(self.SPACES['PASSAGE'])
        if with_exits:
            nodes = nodes.union(self.open_exits)
        if with_walls:
            nodes = nodes.union(self.SPACES['WALL'])
        self.reachable = nx.subgraph(self.graph, nodes)
        if with_passages:
            self.reachable = nx.compose(self.passage_graph, self.reachable)
        
    def compute_radial_lights(self, time):
        """Lights are ON prior to a given shutoff."""
        self.lights_on = set()
        self.lights_off = set()
        for token in self.tokens['LIGHT']:
            for space in self.graph.neighbors(token):
                if self.graph.nodes[space]['SPACE_TYPE'] != 'WALL':
                    raise Exception('Light token on non-wall space')
                self.centers[token] = self.centers[space]
                if self.graph.node[token]['shutoff'] > time:
                    self.lights_on.add(space)
                else:
                    self.lights_off.add(space)

    def compute_light_beams(self):
        """Beams come from tokens now!"""
        for emitter, direction in nx.get_node_attributes(self.graph, 'beam').items():
            source = next(self.graph.neighbors(emitter))
            beam_nodes = list()  # Don't include the source node!
            # Fake vector addition
            beam_node = tuple([p[0]+p[1] for p in zip(source, direction)])
            while beam_node in self.SPACES['FLOOR'].union(self.SPACES['PASSAGE']):
                self.revealed.add(beam_node)
                beam_nodes.append(beam_node)
                beam_node = tuple([p[0]+p[1] for p in zip(beam_node, direction)])
            self.beams = {source: beam_nodes}

    def compute_revealed_spaces(self):
        check_these = self.SPACES['FLOOR'].union(self.SPACES['PASSAGE'])
        # Revealed by radial lights
        for space in self.lights_on:
            for adj_node in self.graph.neighbors(space):
                if adj_node in check_these:
                    self.revealed.add(adj_node)
        # Revealed by adjacent characters
        for character in nx.get_node_attributes(self.graph, 'char_id').keys():
            space = next(self.graph.neighbors(character))
            for adj_node in self.graph.neighbors(space):
                if adj_node in check_these:
                    self.revealed.add(adj_node)

    def draw_with_nx(self):
        centers = self.centers

        # Walkable spaces, including passage entrances
        F = nx.subgraph(self.graph, self.SPACES['FLOOR'].union(self.SPACES['PASSAGE']))
        nx.draw_networkx(F, centers, with_labels=False, node_color=COLOR['FLOOR'],
                         edge_color=COLOR['FLOOR'], width=7)
        # Walls
        nx.draw_networkx_nodes(self.graph, centers, nodelist=self.SPACES['WALL'],
                node_color=COLOR['WALL'], node_size = 450)
        
        # Doors and passages
        nx.draw(self.passage_graph, centers, node_size=240, node_color=COLOR['PASSAGE'],
                edge_color=COLOR['PASSAGE'], width=2)

        # Radial lights
        for node in self.lights_on:
            litnodes = [node] + [node2 for node2 in self.graph.neighbors(node) if node2 in self.revealed]
            nx.draw(nx.subgraph(self.graph, litnodes), centers, node_color=COLOR['LIGHT_ON'], node_size=150,
                    edge_color=COLOR['LIGHT_ON'], width=3)
        nx.draw_networkx_nodes(self.graph, centers, nodelist=self.lights_off,
                               node_color=COLOR['LIGHT_OFF'], node_size=125)
        
        # Light beam
        for source, beam in self.beams.items():
            if beam:
                nx.draw(nx.subgraph(self.graph, [source]+beam), centers, nodelist=beam,
                        node_size=105, node_color=COLOR['BEAM'], edge_color=COLOR['BEAM'], width=3)
                
        # Open exits
        for node in self.open_exits:
            nx.draw(self.graph, centers, nodelist=[node], node_color=COLOR['EXIT_OPEN'],                   
                    edgelist=self.graph.edges(node), edge_color=COLOR['EXIT_OPEN'], width=3)
        # Closed exits
        for node in self.closed_exits:
            nx.draw(self.graph, centers, nodelist=[node], node_color=COLOR['EXIT_CLOSED'],
                    edgelist=self.graph.edges(node), edge_color=COLOR['EXIT_CLOSED'], width=3)


###################
# Initial Testing
###################
theboard = HexBoard()
theboard.load_board(BOARD_FILE)
theboard.load_tokens(TOKEN_FILE)
theboard.compute_exits()
theboard.compute_passages()
theboard.update_reachable()
theboard.compute_radial_lights(0)
theboard.compute_light_beams()
theboard.compute_revealed_spaces()
theboard.draw_with_nx()
nx.draw_networkx_nodes(theboard.graph, theboard.centers, theboard.revealed, node_size=70, node_color='#eeeeee')

#################################
# Which spaces can I move to demo
#################################
theboard.update_reachable(with_exits=True, with_passages=True)
# Subgraph of other walkable nodes within edge distance 3
K = nx.ego_graph(theboard.reachable, (1,1), 3)
nx.draw(K, theboard.centers, node_size=50, node_color='#1122aa')

plt.show()
