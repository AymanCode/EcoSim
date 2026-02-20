import { CubejsApi } from '@cubejs-client/core';

const apiUrl = process.env.CUBE_API_URL || '';
const cubeToken = process.env.CUBE_API_TOKEN || '';

let cubeApi = null;
if (apiUrl && cubeToken) {
  cubeApi = new CubejsApi(cubeToken, { apiUrl });
}

function requireClient() {
  if (!cubeApi) {
    throw new Error(
      'Cube client is not configured. Set CUBE_API_URL and CUBE_API_TOKEN in your environment.'
    );
  }
  return cubeApi;
}

export async function government() {
  const query = {
    dimensions: ['Artworks.year'],
    measures: ['Artworks.population', 'Artworks.GDP'],
  };

  const resultSet = await requireClient().load(query);

  return resultSet.tablePivot().map((row) => ({
    year: parseInt(row['Artworks.year'], 10),
    gdp: parseInt(row['Artworks.GDP'], 10),
    population: parseInt(row['Artworks.population'], 10),
  }));
}

export async function corporation() {
  const query = {
    dimensions: ['Artworks.year'],
    measures: ['Artworks.population'],
  };

  const resultSet = await requireClient().load(query);

  return resultSet.tablePivot().map((row) => ({
    year: parseInt(row['Artworks.year'], 10),
    population: parseInt(row['Artworks.population'], 10),
  }));
}

export async function workers() {
  const query = {
    dimensions: ['Artworks.year'],
    measures: ['Artworks.compensation', 'Artworks.enjoyment'],
  };

  const resultSet = await requireClient().load(query);

  return resultSet.tablePivot().map((row) => ({
    year: parseInt(row['Artworks.year'], 10),
    compensation: parseInt(row['Artworks.compensation'], 10),
    enjoyment: parseInt(row['Artworks.enjoyment'], 10),
  }));
}
