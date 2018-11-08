"""
Filter
Kalman filter implementation.
"""

from pykalman import KalmanFilter

class Filter(object):
	def __init__(self, first_obs):
		self.transition_covariance = 0.8
		self.observation_covariance = 0.8

		self.state = first_obs
		self.measurements = [first_obs]
		self.covariance = None

		self.transition_matrices = [0.8]
		self.observation_matrices = [0.8]
		self.initial_state_mean = [first_obs]
		self.kf = KalmanFilter(
			# self.transition_matrices, 
			# observation_matrices=self.observation_matrices,
			initial_state_mean=0,
			n_dim_state=1,
			# self.transition_covariance,
			observation_covariance=self.observation_covariance)

		# self.state, self.covariance = self.kf.filter(self.measurements)
		# self.state = self.state[0]
		# self.covariance = self.covariance[0][0]

	def update(self, rssi):
		# self.state = self.kf.filter([rssi])[0][0][0]
		self.measurements = self.measurements[-5:]
		self.measurements.append(rssi)
		means, covariances = self.kf.filter(self.measurements)

		self.state, self.covariance = self.kf.filter_update(
    		means[-1], covariances[-1], [rssi])
		self.state = self.state[0]
		self.covariance = self.covariance[0][0]

	# def update(self, rssi):
	# 	self.state, self.covariance = self.kf.filter_update(
 #    		[self.state], [self.covariance], [rssi])
	# 	try:
	# 		self.state = self.state[0][0]
	# 	except:
	# 		self.state = self.state[0]
	# 	self.covariance = self.covariance[0][0]

	def transition_function(self):
		return

	def observation_functions(self):
		return