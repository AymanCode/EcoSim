// Friendly, deterministic names. The server calls households "Subject-<id>" and
// firms by their good ("FoodCo1", "BaselineHousing"); newcomers see people and
// shops instead. The same id gives the same name in every town, so matched
// towns line up.

export const FIRST_NAMES = [
  'Lena', 'Dev', 'Amara', 'Tomas', 'Priya', 'Marcus', 'June', 'Rafael', 'Noor', 'Kofi',
  'Ines', 'Hiro', 'Maya', 'Omar', 'Sofia', 'Ravi', 'Elena', 'Kwame', 'Aisha', 'Mateo',
  'Yuki', 'Nadia', 'Felix', 'Zara', 'Diego', 'Leila', 'Sam', 'Ana', 'Jonah', 'Mei',
  'Tariq', 'Clara', 'Luis', 'Freya', 'Ade', 'Hana', 'Ivan', 'Rosa', 'Kenji', 'Lucia',
  'Emeka', 'Ida', 'Arjun', 'Nora', 'Pablo', 'Sana', 'Theo', 'Ayla', 'Musa', 'Greta',
  'Chen', 'Maria', 'Bilal', 'Elise', 'Joao', 'Farah', 'Nils', 'Imani', 'Pedro', 'Wen',
  'Asha', 'Leo', 'Fatima', 'Oscar', 'Mina', 'Jamal', 'Vera', 'Kai', 'Lola', 'Idris',
  'Esther', 'Raj', 'Nina', 'Tobias', 'Leah', 'Amir', 'Selin', 'Hugo', 'Grace', 'Yusuf',
  'Alma', 'Emil', 'Zainab', 'Victor', 'Olga', 'Kemal', 'Ruth', 'Dario', 'Nia', 'Ben',
  'Carmen', 'Tunde', 'Eva', 'Sami', 'Beatriz', 'Ali', 'Iris', 'Nikhil', 'Anya', 'Jude',
  'Sara', 'Karim', 'Mila', 'Andre', 'Daisy', 'Hamza', 'Lina', 'Oren', 'Paula', 'Mohan',
  'Ruby', 'Enzo', 'Ayesha', 'Liam', 'Tess', 'Abebe', 'Irene', 'Rohan', 'Signe', 'Kaito',
]

// Stepping through a list by a stride coprime with its length visits every
// entry once, so neighbouring ids get unrelated names and the first N ids never
// repeat.
function pick(list, id, stride, offset) {
  const n = Math.abs(Math.trunc(Number(id))) || 0
  return list[(n * stride + offset) % list.length]
}

export function householdName(id) {
  return pick(FIRST_NAMES, id, 37, 11)
}

const PLACES = [
  'Harbor', 'Riverside', 'Oak', 'Elm Street', 'Northside', 'Hillcrest', 'Maple', 'Cedar',
  'Lakeside', 'Union', 'Bridge', 'Mill Lane', 'Station', 'Parkview', 'Old Town', 'Southgate',
]

const TRADES = {
  Food: ['Grocers', 'Bakery', 'Market', 'Deli', 'Pantry', 'Fresh Foods'],
  Housing: ['Homes', 'Rentals', 'Lettings', 'Builders', 'Properties', 'Housing'],
  Services: ['Garage', 'Laundry', 'Repairs', 'Salon', 'Print Shop', 'Couriers'],
  Healthcare: ['Clinic', 'Medical', 'Pharmacy', 'Dental', 'Health Centre', 'Care'],
  PublicWorks: ['Works Crew', 'Works Depot', 'Roads Team', 'Parks Crew', 'Repair Crew', 'Builders Yard'],
  Other: ['Trading', 'Supply Co.', 'Works', 'Goods', 'Company', 'Exchange'],
}

const SECTOR_NAMES = Object.keys(TRADES).filter(sector => sector !== 'Other')

// 16 places x 6 trades = 96 names per sector. Entry k pairs place k % 16 with
// trade (5a + b) % 6 for k = 16a + b, which is one-to-one, and neighbours
// differ in both words.
const NAME_LISTS = Object.fromEntries(Object.entries(TRADES).map(([sector, trades]) => [
  sector,
  Array.from({ length: PLACES.length * trades.length }, (_, k) => {
    const a = Math.floor(k / PLACES.length)
    const b = k % PLACES.length
    return `${PLACES[b]} ${trades[(5 * a + b) % trades.length]}`
  }),
]))

export function firmNamesFor(sector) {
  return NAME_LISTS[sector] ?? NAME_LISTS.Other
}

// Good names encode the sector ("FoodCo1", "ServicesProduct9", "BaselineFood",
// "PublicWorks12"), so events without a sector still name the firm the same way.
function inferSector(name) {
  const bare = String(name ?? '').replace(/^Baseline/, '')
  return SECTOR_NAMES.find(sector => bare.startsWith(sector)) ?? null
}

const BASELINE_LABEL = { PublicWorks: 'Public Works' }

export function firmDisplayName(firm) {
  const name = firm?.name ?? ''
  const sector = firm?.sector || inferSector(name) || 'Other'
  const isBaseline = firm?.isBaseline ?? name.startsWith('Baseline')
  if (isBaseline) return `Town ${BASELINE_LABEL[sector] ?? sector} Co-op`
  return pick(firmNamesFor(sector), firm?.id, 7, 3)
}
