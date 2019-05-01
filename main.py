import logging
import matplotlib.pyplot as plt
import networkx as nwx
from time import sleep
from typing import List, Tuple
from random import randint

# Constants
RIP_INF = 16
RIP_UPDATE_INTERVAL = 30
RIP_TIMEOUT = 180
RIP_GARBAGE_COLLECTION = 120

# Initialize logging
logger = logging.getLogger('main')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# https://tools.ietf.org/html/rfc1058#section-2

class TableEntry:
    def __init__(self, destination: str, hops: int, next_router: str = None, has_changed: bool = False):
        self.destination = destination
        self.hops = hops
        self.has_changed = has_changed
        self.next_router = next_router

    def __str__(self):
        return \
            f"To: {self.destination: <10} " \
                f"Hops: {self.hops: >2} " \
                f"Next: {(self.next_router or '-'): <10} " \
                f"Changed: {self.has_changed: >2}"


class Router:
    def __init__(self, name: str):
        logger.debug(f"Router {name} init called")
        self.name = name

        self.ticks_to_update = 0
        self.reset_update_interval()

        self.broadcast_queue: List[TableEntry] = []
        self.receive_queue: List[Tuple[str, List[TableEntry]]] = []

        self.routing_table: List[TableEntry] = []
        self.routing_table.append(TableEntry(name, 0))  # myself

    def tick(self):
        logger.debug(f"Router {self.name} is ticking...")

        self.ticks_to_update -= 1

        if self.ticks_to_update == 0:
            # Network will handle broadcast
            self.broadcast_queue = self.routing_table

        # Handle update
        if self.receive_queue:
            for received_item in self.receive_queue:
                source, table_entries = received_item
                # self.update_entry(TableEntry(source, 0, source), source)  # Neighbor
                for entry in table_entries:
                    self.update_entry(entry, source)  # (TableEntry(entry.destination, entry.hops + 1, source), source)

            self.receive_queue = []

        if self.ticks_to_update == 0:
            self.reset_update_interval()

        logger.debug(f"Router {self.name} ticking end.")

    def reset_update_interval(self):
        self.ticks_to_update = RIP_UPDATE_INTERVAL + randint(-5, 5)
        logger.debug(f"Reset ticks to update to {self.ticks_to_update}")

    def update_entry(self, entry: TableEntry, source: str):
        logger.debug(f"Updating entry {entry.destination}")

        hops = min(entry.hops + 1, RIP_INF)
        if entry.next_router == self.name:
            # Poison
            hops = RIP_INF

        existing_entry = self.get_entry(entry.destination)
        if existing_entry:
            if entry.hops + 1 < existing_entry.hops:
                existing_entry.next_router = source
                existing_entry.hops = hops
                existing_entry.has_changed = True
                logger.info(f"Updated entry of {self.name} to {entry.destination} because found faster route ({hops}")
        else:
            self.routing_table.append(TableEntry(entry.destination, hops, source))  # todo; changed=true?
            logger.info(f"Added new route to {self.name}: {entry.destination} ({hops} hops)")

    def get_entry(self, destination: str):
        for entry in self.routing_table:
            if entry.destination == destination:
                return entry
        return None

    def __eq__(self, other):
        return self.name == other.name

    def __str__(self):
        return f"Router '{self.name}', table:\r\n" + "\r\n".join(str(x) for x in self.routing_table)


class Network:
    routers: List[Router] = []
    routes: List[Tuple[str, str]] = []

    def add_router(self, router_name: str):
        router = Router(router_name)
        # check if already exists, etc.
        if router in self.routers:
            print("Cannot add router, it already exists")
            return
        self.routers.append(router)

    def add_route(self, first: str, second: str):
        if not self.find_router(first):
            print(f"Cannot add route, router '{first}' doesn't exist")
            return
        if not self.find_router(second):
            print(f"Cannot add route, router '{second}' doesn't exist")
            return

        route = (first, second)

        if route in self.routes:
            print("Cannot add route, it already exists")
            return

        self.routes.append(route)
        logger.info(f"Added route to network: {route}")

    def find_router(self, name: str):
        return ([x for x in self.routers if x.name == name] or [None])[0]

    def route_exists(self, first: str, second: str):
        return (first, second) in self.routes or (second, first) in self.routes

    def delete_route(self, first: str, second: str):
        if not self.route_exists(first, second):
            print("Cannot delete route, it doesn't exist")
            return

        if (first, second) in self.routes:
            self.routes.remove((first, second))
        elif (second, first) in self.routes:
            self.routes.remove((second, first))

        logger.info(f"Network route {(first, second)} removed")

    def delete_router(self, router_name: str):
        if router_name not in [x.name for x in self.routers]:
            print("Cannot delete router, it doesn't exist")
            return

        index = 0
        for i in range(len(self.routers)):
            if self.routers[i].name == router_name:
                break

        for router in self.routers:
            if self.route_exists(router_name, router.name):
                self.delete_route(router_name, router.name)
                logger.info(f"Deleting routers {router_name} route: {router_name, router.name}")

        logger.info(f"Deleting router {self.routers[index]}")
        del self.routers[index]

    def tick(self):
        logger.debug("Network ticking...")

        for router in self.routers:
            router.tick()
            if router.broadcast_queue:
                self.broadcast(router)
                router.broadcast_queue = None

        logger.debug("Network ticking end.")

    def broadcast(self, router: Router):
        for other_router in self.routers:
            if self.route_exists(router.name, other_router.name):
                other_router.receive_queue.append((router.name, router.broadcast_queue))
                logger.info(f"Router {other_router.name} received broadcast from {router.name}")


if __name__ == '__main__':

    print(
        """
    Commands:
        add router <name>
        add route <first> <second> -- add route between routers, bi-directional
        delete router <name>
        delete route <first> <second>     
           
        tick <seconds: int> -- simulate <seconds> ticks, one second is one tick
        delay <seconds: float> -- delay between ticks

        # TODO: 
        send <from> <to> -- simulate sending of a packet, packet travels with a speed of <delay> (default = 1)

        print -- print network routers and their tables
        show -- show graph of current network
        loglevel <level> -- change logging level: debug, info, error
        
        """
    )
    sleep(0.2)


    network = Network()
    network.add_router("a")
    network.add_router("b")
    network.add_router("c")
    network.add_router("d")
    network.add_route("a", "b")
    network.add_route("b", "c")
    network.add_route("c", "d")
    for i in range(100):
        network.tick()

    network.add_route("a", "d")


    tick_delay = 0
    while True:
        try:
            sleep(0.1)
            command = input("Enter command: \r\n").strip()
            command_lower = command.lower()
            if command_lower.startswith("add router"):
                name = command.split(" ")[-1]
                network.add_router(name)
            elif command_lower.startswith("add route"):
                first, second = command.split(" ")[-2:]
                network.add_route(first, second)
            elif command_lower.startswith("delete router"):
                name = command.split(" ")[-1]
                network.delete_router(name)
            elif command_lower.startswith("delete route"):
                first, second = command.split(" ")[-2:]
                network.delete_route(first, second)

            elif command_lower.startswith("print"):
                for router in network.routers:
                    print(router)
            elif command_lower.startswith("show"):
                graph = nwx.Graph()
                graph.add_nodes_from([x.name for x in network.routers])
                graph.add_edges_from(network.routes)
                nwx.draw(graph, with_labels=True)
                plt.show()

            elif command_lower.startswith("tick"):
                count = int(command.split(" ")[-1])
                print("Ticking...")
                sleep(0.05)
                for i in range(count):
                    if (tick_delay > 0):
                        print(f"Tick {i}")
                        sleep(tick_delay)
                    sleep(0.05)
                    network.tick()
                print("Ticking end.")

            elif command_lower.startswith("delay"):
                amount = float(command.split(" ")[-1])
                tick_delay = amount

            elif command_lower.startswith("loglevel"):
                level = command.split(" ")[-1].upper()
                level_int = logging._nameToLevel.get(level)
                logger.setLevel(level_int)

            else:
                print("Command not found, please try again.")

        except Exception as e:
            print(f"Error occurred: {e}. \r\nPlease try again.")

