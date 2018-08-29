#! /usr/bin/env python3

"""
Infinite Fun Space

Tri-Peter Shrive
tri.shrive@gmail.com

TODO:
	* gravity,
	* friction,
	* guidance (should compensate for gravity),
	* collision detection,
	* radar,
	* database,
	* web sockets
"""

import curses
import enum
import queue
import logging
import numpy as np
import os 
import threading

logging.basicConfig(
		filename = "ifs.log",
		filemode = "w",
		level = logging.DEBUG
		)

logger = logging.getLogger(__name__)

@enum.unique
class Message(enum.Enum):
	"""
	"""
	open_Window = 0
	add = 1
	update_Board = 2
	update_Piece = 3
	move_Order = 4

class Piece:
	"""
	"""
	def __init__(
		self,
		position: np.array,
		speed: np.array
		):
		"""
		"""
		self.position = position
		self.speed = speed

	def move_Order(
		self,
		destination: np.array,
		) -> None:
		"""
		"""
		self.destination = destination

	def update(
		self
		) -> None:
		"""
		"""
		pass

class Rocket(Piece):
	"""
	"""
	def __init__(
		self,
		position: np.array,
		speed: np.array,
		mass: np.float64 = 1.0,
		final_mass: np.float64 = 0.1,
		exit_velocity: np.float64 = 1.0,
		mass_flow_rate: np.float64 = 0.001
		):
		"""
		"""
		Piece.__init__(
			self,
			position,
			speed
			)
		self.mass = mass
		self.final_mass = final_mass
		self.exit_velocity = exit_velocity
		self.mass_flow_rate = mass_flow_rate

		total_speed = np.sum(np.abs(self.speed))
		if(0 < total_speed):
			self.direction = self.speed / float(total_speed)
	def update(
		self
		) -> None:
		"""
		"""
		self.thrust = self.exit_velocity * self.mass_flow_rate
		assert(0 < self.mass_flow_rate)
		assert(self.mass_flow_rate < self.mass)
		self.acceleration = self.thrust / float(self.mass)
		# do we have a destination?
		if("destination" in self.__dict__):
			direction = self.destination - self.position
			sum_direction = np.sum(np.abs(direction))
			if(0 < sum_direction):
				# unit vector
				self.direction = direction / float(sum_direction)
				# do we still have fule?
				if(self.mass > self.final_mass):
					self.speed = self.speed + self.direction * self.acceleration
					self.mass = self.mass - self.mass_flow_rate
		self.position = self.position + self.speed

class Message_Bus:
	"""
	"""
	def __init__(
		self,
		Queue,
		callbacks: list,
		num_threads: int = 4
		):
		"""
		"""
		self.Queue = Queue
		self.callbacks = callbacks
		for i in range(num_threads):
			worker = threading.Thread(
					target = self.__get_Message, 
					args = (self.Queue,)
					)
			worker.setDaemon(True)
			worker.start()

	def __get_Message(
		self,
		Queue: queue.Queue
		) -> None:
		"""
		"""
		while(True):
			item = Queue.get()
			Msg = item[0]
			args = item[1]
			for callback in self.callbacks:
				callback.handle_Message(Msg, args)
			Queue.task_done()

	def post_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		"""
		self.Queue.put((Msg, args))

class System:
	"""
	"""
	def __init__(
		self,
		Framework,
		Queue: queue.Queue
		):
		"""
		"""
		self.Queue = Queue
		self.Framwork = Framework

	def post_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		"""
		self.Queue.put((Msg, args))
		
	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		"""
		pass

class Interface(System):
	"""
	"""
	def __init__(
		self,
		Framework,
		Queue
		):
		"""
		"""
		System.__init__(self, Framework, Queue)

	def open_Window(
		self
		) -> None:
		"""
		"""
		curses.wrapper(self.run)

	def run(
		self,
		stdscr
		) -> None:
		"""
		"""
		key = ""
		while(True):
			curses.noecho()
			stdscr.clear()
			self.post_Message(Message.update_Board)
			Queue.join()
			self.draw_Board(stdscr)
			stdscr.refresh()
			if(":" == key):
				stdscr.addch(stdscr.getmaxyx()[0] - 1, 0, ":")
				curses.echo()
				s = stdscr.getstr().decode(encoding="utf-8")
				s = s.split(" ")
				if(1 == len(s)):
					args = None
				else:
					args = list()
					for i in range(1, len(s)):
						if("" != s[i]):
							args.append(s[i])

				window_size = stdscr.getmaxyx()
				if("" == s[0]):
					stdscr.addstr(window_size[0] - 1, 0, (window_size[1] - 1) * " ")
					stdscr.move(window_size[0] - 1, 0)
				elif("add" == s[0] and 6 == len(args)):
					stdscr.addstr(window_size[0] - 1, 0, (window_size[1] - 1) * " ")
					stdscr.move(window_size[0] - 1, 0)
					self.post_Message(Message.add, args)
				elif("move" == s[0] and 6 == len(args)):
					stdscr.addstr(window_size[0] - 1, 0, (window_size[1] - 1) * " ")
					stdscr.move(window_size[0] - 1, 0)
					self.post_Message(Message.move_Order, args)
				else:
					stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, "Invalid Input")

			try:
				key = ""
				key = stdscr.getkey()
			except:
				e = sys.exc_info()[0]
				logger.debug(e)
				pass

	def draw_Board(
		self,
		stdscr
		) -> None:
		"""
		"""
		stdscr.addstr("Infinite Fun Space 0.1")
		for i in range(Framework.max_y):
			stdscr.addstr(2 * i + 3, 0, str(i))
		for i in range(Framework.max_x):
			stdscr.addstr(2, 4 * i + 3, str(i))
		for piece in Framework.pieces_List:
			stdscr.addstr(2 * int(np.rint(piece.position[1])) + 3, 4 * int(np.rint(piece.position[0])) + 3, "X" + str(int(np.rint(piece.position[2]))))
		window_size = stdscr.getmaxyx()
		stdscr.move(window_size[0] - 1, 0)

class Logic(System):
	"""
	"""
	def __init__(
		self,
		Framework,
		Queue
		):
		"""
		"""
		System.__init__(self, Framework, Queue)
		
	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		"""
		if(Message.add == Msg):
			self.add(args)
		elif(Message.update_Board == Msg):
			self.update_Board()
		elif(Message.update_Piece == Msg):
			self.update_Piece(args)
		elif(Message.move_Order == Msg):
			self.move_Order(args)
		else:
			pass

	def add(
		self,
		args
		) -> None:
		"""
		"""
		position = np.array((np.rint(args[0]), np.rint(args[1]), np.rint(args[2])), dtype = np.float64)
		speed = np.array((np.rint(args[3]), np.rint(args[4]), np.rint(args[5])), dtype = np.float64)
	
		Framework.pieces_List.append(Rocket(position, speed))
		Framework.board_Map[int(np.rint(args[0])), int(np.rint(args[1])), int(np.rint(args[2]))] = Framework.next_ID
		Framework.next_ID = Framework.next_ID + 1
		
	def move_Order(
		self,
		args
		) -> None:
		"""
		"""
		old_x = int(args[0])
		old_y = int(args[1])
		old_z = int(args[2])

		new_x = int(args[3])
		new_y = int(args[4])
		new_z = int(args[5])
		
		piece_ID = Framework.board_Map[old_x, old_y, old_z]
		destination = np.array((new_x, new_y, new_z), dtype = int)
		Framework.pieces_List[piece_ID].move_Order(destination)

	def update_Board(
		self,
		) -> None:
		"""
		"""
		for piece in Framework.pieces_List:
			self.post_Message(Message.update_Piece, piece)

	def update_Piece(
		self,
		args
		) -> None:
		"""
		"""
		args.update()


class Framework():
	"""
	"""
	def __init__(
		self,
		max_x: int = 10,
		max_y: int = 10,
		max_z: int = 10
		):
		self.max_x = max_x
		self.max_y = max_y
		self.max_z = max_z
		self.board_Map = np.zeros((max_x, max_y, max_z), dtype = int)
		self.pieces_List = list()
		self.next_ID = 0
	
if(__name__ == "__main__"):
	Framework = Framework()
	Queue = queue.Queue(maxsize = 0)
	Logic = Logic(Framework, Queue)
	Interface = Interface(Framework, Queue)
	Message_Bus = Message_Bus(Queue, [Logic, Interface])
	Message_Bus.post_Message(Message.add, [0, 0, 0, 0, 0, 0])
	Message_Bus.post_Message(Message.add, [0, 8, 0, 0, 0, 0])
	Message_Bus.post_Message(Message.add, [8, 0, 0, 0, 0, 0])
	Message_Bus.post_Message(Message.add, [8, 8, 0, 0, 0, 0])
	Queue.join()
	Message_Bus.post_Message(Message.move_Order, [0, 0, 0, 4, 4, 4])
	Message_Bus.post_Message(Message.move_Order, [0, 8, 0, 4, 4, 4])
	Message_Bus.post_Message(Message.move_Order, [8, 0, 0, 4, 4, 4])
	Message_Bus.post_Message(Message.move_Order, [8, 8, 0, 4, 4, 4])
	Queue.join()
	Interface.open_Window()
