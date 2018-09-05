#! /usr/bin/env python3

"""
Infinite Fun Space

Tri-Peter Shrive
tri.shrive@gmail.com

TODO:
	* gravity,
	* drag,
	* guidance (should compensate for external forces),
	* collision detection,
	* radar,
	* infra-red,
	* sonar,
	* database,
	* web sockets,
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
	
class Piece:
	"""
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array
		):
		"""
		"""
		self.piece_id = piece_id
		self.position = position
		self.Framework = Framework
		self.has_destination = False

	def move_Order(
		self,
		destination: np.array
		) -> None:
		"""
		"""
		self.destination = destination
		self.has_destination = True 

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
		piece_id: int,
		Framework: Framework,
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
			piece_id,
			Framework,
			position
			)
		self.speed = speed
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
		logger.debug("rocket in flight")
		self.new_Position()
		for piece in Framework.pieces_List:
			if(piece.piece_id != self.piece_id):
				self.collision_Detection(piece)

	def new_Position(
		self
		) -> None:
		"""
		Newtons method.
		Should use RK4.
		"""
		self.thrust = self.exit_velocity * self.mass_flow_rate
		assert(0 < self.mass_flow_rate)
		assert(self.mass_flow_rate < self.mass)
		self.acceleration = self.thrust / float(self.mass)
		# do we have a destination?
		if(True == self.has_destination):
			self.direction = self.destination - self.position
			sum_direction = np.sum(np.abs(self.direction))
			if(0 < sum_direction):
				# unit vector
				self.direction = self.direction / float(sum_direction)
				# do we still have fule?
				if(self.mass > self.final_mass):
					self.speed = self.speed + self.direction * self.acceleration
					self.mass = self.mass - self.mass_flow_rate
		self.position = self.position + self.speed

	def collision_Detection(
		self,
		piece: Piece
		) -> None:
		"""
		if ( x-cx )^2 + (y-cy)^2 + (z-cz)^ 2 < r^2 
		"""
		blast_radius = 0.5
		logger.debug("rocket {} position {}".format(self.piece_id, self.position))
		logger.debug("target {} position {}".format(piece.piece_id, piece.position))
		kill = np.power((self.position[0] - piece.position[0]), 2) + np.power((self.position[1] - piece.position[1]), 2) + np.power((self.position[2] - piece.position[2]), 2) < np.power(blast_radius, 2)
		logger.debug("kill: {}".format(kill))
		if(piece.piece_id != self.piece_id):
			pass

class Radar(Piece):
	"""
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array,
		speed: np.array
		):
		"""
		"""
		Piece.__init__(
			self,
			piece_id,
			Framework,
			position
			)
		self.visible_pieces = list()
		self.speed = speed
		self.rocket_list = list()
		self.total_rockets = 1

	def update(
		self
		) -> None:
		"""
		"""
		self.visible_pieces = list()
		for piece in self.Framework.pieces_List:
			if(self.piece_id != piece.piece_id):
				if(self.is_Visible(piece)):
					self.visible_pieces.append(piece)

		for piece in self.visible_pieces:
			if(0 < self.total_rockets):
				logger.debug("launching rocket")
				rocket = Rocket(
					self.piece_id,
					self.Framework,
					self.position,
					self.speed
					)
				rocket.move_Order(piece.position)
				self.rocket_list.append(rocket)
			self.total_rockets = self.total_rockets - 1

		for rocket in self.rocket_list:
			rocket.update()

	def is_Visible(
		self,
		piece: Piece
		) -> bool:
		"""
		Line of sight.
		"""
		earth_radius = 6371
		radar_height = 0.001

		radar_position = np.array(self.position, dtype = np.float64)
		radar_position[2] = radar_position[2] + radar_height

		distance = np.linalg.norm(piece.position - radar_position)

		piece_height = piece.position[2]
		radar_height = radar_position[2]

		piece_horizon = np.sqrt(2 * earth_radius * piece_height)
		radar_horizon = np.sqrt(2 * earth_radius * radar_height + radar_height**2)

		if(distance < piece_horizon + radar_horizon):
			is_visible = True
		else:
			is_visible = False
	
		return is_visible

class Ship(Piece):
	"""
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array,
		speed: np.array,
		acceleration: np.float64 = 0.001,
		top_speed: np.float64 = 0.01,
		num_rockets: np.int64 = 3
		):
		"""
		Carries radars and rockets over seas.
		"""
		Piece.__init__(
			self,
			piece_id,
			Framework,
			position
			)
		self.speed = speed
		self.top_speed = top_speed
		self.acceleration = acceleration

		self.radar = Radar(
				piece_id,
				Framework,
				position,
				speed
				)

	def update(
		self
		) -> None:
		"""
		"""
		self.radar.update()

		# do we have a destination?
		if(True == self.has_destination):
			self.direction = self.destination - self.position
			sum_direction = np.sum(np.abs(self.direction))
			if(0 < sum_direction):
				# unit vector
				if(np.linalg.norm(self.speed) < self.top_speed):
					self.speed = self.speed + self.direction * self.acceleration
				else:
					self.speed = self.direction * self.top_speed

		self.position = self.position + self.speed
		self.radar.position = self.position
		self.radar.speed = self.speed

class System:
	"""
	"""
	def __init__(
		self,
		Framework: Framework,
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

class Message_Bus(System):
	"""
	"""
	def __init__(
		self,
		Framework,
		Queue,
		callbacks: list,
		num_threads: int = 4
		):
		"""
		"""
		System.__init__(self, Framework, Queue)
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

	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		"""
		pass

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
			#draw missiles

		window_size = stdscr.getmaxyx()
		stdscr.move(window_size[0] - 1, 0)

	def move_Order(
		self,
		args
		) -> None:
		"""
		"""
		piece_ID = Framework.board_Map[int(args[0]), int(args[1]), int(args[2])]
		destination = np.array((int(args[3]), int(args[4]), int(args[5])), dtype = int)
		Framework.pieces_List[piece_ID].move_Order(destination)

	def add(
		self,
		args
		) -> None:
		"""
		"""
		position = np.array((args[0], args[1], args[2]), dtype = np.float64)
		speed = np.array((args[3], args[4], args[5]), dtype = np.float64)
	
		Framework.pieces_List.append(Ship(Framework, position, speed))
		Framework.board_Map[int(args[0]), int(args[1]), int(args[2])] = Framework.next_ID
		Framework.next_ID = Framework.next_ID + 1
		
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
		elif(Message.move_Order == Msg):
			self.move_Order(args)
		elif(Message.update_Board == Msg):
			self.update_Board()
		elif(Message.update_Piece == Msg):
			self.update_Piece(args)
		else:
			pass

	def update_Board(
		self,
		) -> None:
		"""
		"""
		for piece in Framework.pieces_List:
			self.post_Message(Message.update_Piece, piece)

	def update_Piece(
		self,
		piece
		) -> None:
		"""
		"""
		piece.update()

	def move_Order(
		self,
		args
		) -> None:
		"""
		"""
		old_x = int(args[0])
		old_y = int(args[1])
		old_z = int(args[2])

		new_coords = args[3:6]
		
		piece_ID = Framework.board_Map[old_x, old_y, old_z]
		destination = np.array((new_coords), dtype = np.float64)
		Framework.pieces_List[piece_ID].move_Order(destination)

	def add(
		self,
		args
		) -> None:
		"""
		"""
		position = np.array((args[0], args[1], args[2]), dtype = np.float64)
		speed = np.array((args[3], args[4], args[5]), dtype = np.float64)
	
		Framework.pieces_List.append(Ship(Framework.next_ID, Framework, position, speed))
		Framework.board_Map[int(args[0]), int(args[1]), int(args[2])] = Framework.next_ID
		Framework.next_ID = Framework.next_ID + 1
		
if(__name__ == "__main__"):
	Framework = Framework()
	Queue = queue.Queue(maxsize = 0)
	Logic = Logic(Framework, Queue)
	Interface = Interface(Framework, Queue)
	Message_Bus = Message_Bus(Framework, Queue, [Logic, Interface])
	Message_Bus.post_Message(Message.add, [1, 8, 0, 0, 0, 0])
	Message_Bus.post_Message(Message.move_Order, [1, 8, 0, 7, 2, 0])
	Message_Bus.post_Message(Message.add, [8, 1, 0, 0, 0, 0])
	Queue.join()
	Interface.open_Window()
