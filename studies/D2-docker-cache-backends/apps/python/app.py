import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# d2-change-line: 0
BUILD = 0

x = np.arange(10).reshape(-1, 1)
y = pd.Series(np.arange(10) * 2.0)
print(LinearRegression().fit(x, y).coef_, BUILD)
