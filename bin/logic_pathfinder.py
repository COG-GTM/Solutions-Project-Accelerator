import numpy as np
import pyastar2d

class Pathfinder():
    def __init__(self, image, poi_positions) -> None:
        grid = image.astype(np.float32)
        grid[grid == 255] = np.inf
        grid[grid == 0] = 1

        for i in range(len(poi_positions)):

            start = np.array([poi_positions[i][0], poi_positions[i][1]])

            for j in range(len(poi_positions)):
                end = np.array(poi_positions[j][0], poi_positions[j][1])

                path = pyastar2d.astar_path(grid, start, end, allow_diagonal=True)

                