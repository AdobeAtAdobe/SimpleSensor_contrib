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
		self.transition_matrices = [1]
		self.observation_matrices = [first_obs]
		self.initial_state_mean = [first_obs]
		self.kf = KalmanFilter(
			# self.transition_matrices, 
			observation_matrices=self.observation_matrices,
			n_dim_state=1)
			# self.transition_covariance,
			# observation_covariance=self.observation_covariance)

	def update(self, rssi):
		self.state = self.kf.filter([rssi])[0][0][0]

	def transition_function(self):
		return

	def observation_functions(self):
		return