import numpy as np
import pandas as pd

# data
student = {
    'name': ['John', 'Jay', 'sachin', 'Geetha', 'Amutha', 'ganesh'],
    'gender': ['male', 'male', 'male', 'female', 'female', 'male'],
    'math': [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
}
df = pd.DataFrame(student)

# subset --> check if NaNs change to str 'nan'
where = np.where(df['name'] == 'Geetha', 'Lolmestring', df['math'])
print(where)
print(df) # mask approach stores the NaN correctly
