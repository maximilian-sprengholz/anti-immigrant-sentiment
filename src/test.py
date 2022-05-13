from pandas.api.types import union_categoricals
import pandas as pd

def concat_dfs_with_cat_data(dfs):
    '''
    Concatenate dataframe but keep categorical dtypes.
    Credit: https://stackoverflow.com/a/57809778
    '''
    # Iterate on categorical columns common to all dfs
    for col in set.intersection(
            *[
                set(df.select_dtypes(include='category').columns)
                for df in dfs
            ]
            ):
        # Generate the union category across dfs for this column
        # exclude columns with only NaN, the float64 dtype differs from object
        uc = union_categoricals([df[col] for df in dfs if df[col].isnull().all()==False])
        # Change to union category for all dataframes
        for df in dfs:
            df[col] = pd.Categorical(df[col].values, categories=uc.categories)
    return pd.concat(dfs, ignore_index=True)

df1=pd.DataFrame({'a': [1, 2],
                  'x': pd.Categorical([np.nan, np.nan]),
                  'y': pd.Categorical(['banana', 'bread'])})
df2=pd.DataFrame({'x': pd.Categorical(['rat']),
                  'y': pd.Categorical(['apple'])})

#df['x'].astype(pd.CategoricalDtype(categories=['fuck', 'me']))
concat_dfs_with_cat_data([df1, df2]).dtypes
#print(df1['x'].dtype.categories.dtype)
#print(df2['x'].dtype.categories.dtype)
