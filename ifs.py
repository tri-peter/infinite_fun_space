#! /usr/bin/env python3

"""
Infinite Fun Space

Tri-Peter Shrive
tri.shrive@gmail.com

TODO:
	* add external forces  (gravity, drag, etc.)
	* improve guidance (should compensate for external forces),
	* improve collision detection,
	* list of friendlies,
	* remove piece when killed,
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
	Valid messages for sent between systems via the message bus.
	"""
	open_Window = 0
	add = 1
	update_Board = 2
	update_Piece = 3
	move_Order = 4

class Framework():
	"""
	Encapsulates data shared by the systems and provides locking mechanism.
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
		self.board_Map[:] = -1
		self.pieces_List = list()
		self.next_ID = 0
		self.lock = threading.BoundedSemaphore()
	
class Piece:
	"""
	Basic board piece.
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array
		):
		"""
		Set initial piece data and reference framework for future reference to shared data.
		"""
		self.piece_id = piece_id
		self.position = position
		self.has_destination = False
		self.Framework = Framework

	def move_Order(
		self,
		destination: np.array
		) -> None:
		"""
		Set destination used when updating piece.
		"""
		self.destination = destination
		self.has_destination = True 

	def update(
		self
		) -> None:
		"""
		Basic piece does nothing.
		"""
		pass

class Rocket(Piece):
	"""
	The rocket piece. Is fired by radar and then moves to target.
	At the moment rockets are fire and forget with no retargeting if target moves.
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
		Set piece data and additional rocket specific data.
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

	def update(
		self
		) -> None:
		"""
		Update rocket position and check for collision with target.
		Currently targets anything but the piece that launched it...
		"""
		self.new_Position()
		for piece in Framework.pieces_List:
			# TODO: list of friendlies
			if(piece.piece_id != self.piece_id):
				self.collision_Detection(piece)

	def new_Position(
		self
		) -> None:
		"""
		Uses Newtons method to update rocket position.
		Should use Runga-Kutta 4th order method.

		Rocket has variable mass. Acceleration increases as mass decreases.
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
		Check if piece is inside blast radius centered at rockets location.
		"""
		blast_radius = 0.5
		logger.debug("rocket {} position {}".format(self.piece_id, self.position))
		logger.debug("target {} position {}".format(piece.piece_id, piece.position))
		kill = np.power((self.position[0] - piece.position[0]), 2) + np.power((self.position[1] - piece.position[1]), 2) + np.power((self.position[2] - piece.position[2]), 2) < np.power(blast_radius, 2)
		logger.debug("target {} kill: {}".format(piece.piece_id, kill))
		if(piece.piece_id != self.piece_id):
			pass

class Radar(Piece):
	"""
	The radar piece. Detects enemy ships and fires rockets at them.
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array,
		speed: np.array
		):
		"""
		Set piece data and additional radar specific data.
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
		Update launched rocket and list of visible pieces.
		Launch rockets at visible pieces if rockets are available.
		"""
		self.visible_pieces = list()
		for piece in self.Framework.pieces_List:
			# TODO: list of friendlies
			if(self.piece_id != piece.piece_id):
				if(self.is_Visible(piece)):
					self.visible_pieces.append(piece)

		for piece in self.visible_pieces:
			if(0 < self.total_rockets):
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
		Check for line of sight. Only takes horizon into account.
		"""
		# TODO: check for hills
		# TODO: check radar sensitivity against targets radar-cross-section
		planet_radius = 6371
		radar_height = 0.005

		radar_position = np.array(self.position, dtype = np.float64)
		radar_position[2] = radar_position[2] + radar_height

		distance = np.linalg.norm(piece.position - radar_position)

		piece_height = piece.position[2]
		radar_height = radar_position[2]

		piece_horizon = np.sqrt(2 * planet_radius * piece_height)
		radar_horizon = np.sqrt(2 * planet_radius * radar_height + radar_height**2)

		if(distance < piece_horizon + radar_horizon):
			is_visible = True
		else:
			is_visible = False
	
		return is_visible

class Ship(Piece):
	"""
	The ship piece. Transports radar and rockets.
	"""
	def __init__(
		self,
		piece_id: int,
		Framework: Framework,
		position: np.array,
		speed: np.array,
		acceleration: np.float64 = 0.0001,
		top_speed: np.float64 = 0.001,
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

	def new_Position(
		self
		) -> None:
		"""
		Uses Newtons method to update rocket position.
		Should use Runga-Kutta 4th order method.

		Ship acceleration is constant.
		Ship has a top speed.
		"""
		temp_x = int(self.position[0])
		temp_y = int(self.position[1])
		temp_z = int(self.position[2]) 

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
		with Framework.lock:
			self.Framework.board_Map[temp_x, temp_y, temp_z] = -1
			self.Framework.board_Map[int(self.position[0]), int(self.position[1]), int(self.position[2])] = self.piece_id 

	def update(
		self
		) -> None:
		"""
		Update ship and radar position.
		Update radar and associated rockets. 
		"""
		self.new_Position
		self.radar.position = self.position
		self.radar.speed = self.speed
		self.radar.update()

class System:
	"""
	Basic system.
	"""
	def __init__(
		self,
		Framework: Framework,
		Queue: queue.Queue
		):
		"""
		Set threading queue and framework for later use.
		"""
		self.Queue = Queue
		self.Framwork = Framework

	def post_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		Post a message via the message bus.
		Uses a queue to allocate tasks to threads.
		"""
		self.Queue.put((Msg, args))
		
	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		Handle a message from the message bus.
		Here all messages are ignored.
		"""
		pass

class Message_Bus(System):
	"""
	Passes messages between systems.
	"""
	def __init__(
		self,
		Framework,
		Queue,
		callbacks: list,
		num_threads: int = 4
		):
		"""
		Initialise the basic system and set callback systems.
		Callback systems are those that recieve messages.
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
		Get messages directly from the queue and pass them on to the callback systems.
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
	Curses graphical user interface.
	"""
	def __init__(
		self,
		Framework,
		Queue
		):
		"""
		Initialise the basic system.
		"""
		System.__init__(self, Framework, Queue)

	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		Ignore all messages.
		"""
		pass

	def open_Window(
		self
		) -> None:
		"""
		Start the curses window.
		"""
		curses.wrapper(self.run)

	def run(
		self,
		stdscr
		) -> None:
		"""
		The game loop.
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
		Draw the game board and add pieces.
		"""
		stdscr.addstr("Infinite Fun Space 0.1")
		for i in range(Framework.max_y):
			stdscr.addstr(2 * i + 3, 0, str(i))
		for i in range(Framework.max_x):
			stdscr.addstr(2, 4 * i + 3, str(i))
		for piece in Framework.pieces_List:
			for rocket in piece.radar.rocket_list:
				with(Framework.lock):
					temp_x = int(rocket.position[0])
					temp_y = int(rocket.position[1])
					temp_z = int(rocket.position[2])
					if(-1 == Framework.board_Map[temp_x, temp_y, temp_z]):
						stdscr.addstr(2 * temp_y + 3, 4 * temp_x + 3, "." + str(temp_z))
					elif(-1 == Framework.board_Map[temp_x + 1, temp_y, temp_z]):
						temp_x = temp_x + 1
						stdscr.addstr(2 * temp_y + 3, 4 * temp_x + 3, "." + str(temp_z))
					elif(-1 == Framework.board_Map[temp_x - 1, temp_y, temp_z]):
						temp_x = temp_x - 1
						stdscr.addstr(2 * temp_y + 3, 4 * temp_x + 3, "." + str(temp_z))
					elif(-1 == Framework.board_Map[temp_x, temp_y + 1, temp_z]):
						temp_y = temp_y + 1
						stdscr.addstr(2 * temp_y + 3, 4 * temp_x + 3, "." + str(temp_z))
					elif(-1 == Framework.board_Map[temp_x, temp_y - 1, temp_z]):
						temp_y = temp_y - 1
						stdscr.addstr(2 * temp_y + 3, 4 * temp_x + 3, "." + str(temp_z))
					logger.debug("rocket printed ({}, {}, {})".format(temp_x, temp_y, temp_z))
			
					
			stdscr.addstr(2 * int(piece.position[1]) + 3, 4 * int(piece.position[0]) + 3, "X" + str(int(piece.position[2])))

		window_size = stdscr.getmaxyx()
		stdscr.move(window_size[0] - 1, 0)

class Logic(System):
	"""
	The game logic.
	"""
	def __init__(
		self,
		Framework,
		Queue
		):
		"""
		Initialise the basic system.
		"""
		System.__init__(self, Framework, Queue)
		
	def handle_Message(
		self,
		Msg: Message,
		args: list = None
		) -> None:
		"""
		Pass relevant messages and args onto the associated methods.
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
		Update all pieces on the board.
		"""
		for piece in Framework.pieces_List:
			self.post_Message(Message.update_Piece, piece)

	def update_Piece(
		self,
		piece
		) -> None:
		"""
		Update a single piece.
		"""
		piece.update()

	def move_Order(
		self,
		args
		) -> None:
		"""
		Get piece id using board map and use it to give that piece a move order.
		"""
		old_x = int(args[0])
		old_y = int(args[1])
		old_z = int(args[2])

		new_coords = args[3:6]
		destination = np.array((new_coords), dtype = np.float64)
		with(Framework.lock):
			piece_ID = Framework.board_Map[old_x, old_y, old_z]
			piece = Framework.pieces_List[piece_ID]

		piece.move_Order(destination)

	def add(
		self,
		args
		) -> None:
		"""
		Add a new piece to the board.
		"""
		position = np.array((args[0], args[1], args[2]), dtype = np.float64)
		speed = np.array((args[3], args[4], args[5]), dtype = np.float64)
		with(Framework.lock):
			Framework.pieces_List.append(Ship(Framework.next_ID, Framework, position, speed))
			Framework.board_Map[int(args[0]), int(args[1]), int(args[2])] = Framework.next_ID
			Framework.next_ID = Framework.next_ID + 1
		
if(__name__ == "__main__"):
	Framework = Framework()
	Queue = queue.Queue(maxsize = 0)
	Logic = Logic(Framework, Queue)
	Interface = Interface(Framework, Queue)
	Message_Bus = Message_Bus(Framework, Queue, [Logic, Interface])
	Message_Bus.post_Message(Message.add, [1, 5, 0, 0, 0, 0])
	Message_Bus.post_Message(Message.add, [8, 5, 0, 0, 0, 0])
	Queue.join()
	Interface.open_Window()
