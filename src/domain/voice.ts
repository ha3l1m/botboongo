import { menuItem, type Flavor } from './menu'
import { addToCart, type Cart } from './order'
import { closestFlavor } from './sounds'

/** A word that was not a menu name but sounded like one, and what it was taken for. */
export type Guess = { heard: string; flavor: Flavor }

export type VoiceResult = {
  cart: Cart
  unavailable: Flavor[]
  clipped: boolean
  guessed: Guess[]
  /** Flavors the customer said to leave out ("슈크림은 빼고"). */
  removed: Flavor[]
}

type Token = { kind: 'flavor'; flavor: Flavor } | { kind: 'count'; value: number }

const WORD_COUNTS: Record<string, number> = {
  하나: 1, 둘: 2, 셋: 3, 넷: 4, 다섯: 5, 여섯: 6, 일곱: 7, 여덟: 8, 아홉: 9,
  한: 1, 두: 2, 세: 3, 네: 4, 석: 3, 넉: 4,
  일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 칠: 7, 팔: 8, 구: 9, 십: 10,
}

/**
 * Short forms (한/두/세/네) and sino numbers only count when a counter follows, so the 세 of "주세요"
 * and the 이 of "팥붕이" are not read as numbers.
 */
const TOKEN = new RegExp(
  [
    // spellings the recognizer is known to produce; longer ones first, the one-syllable fallback last
    '(?<choco>초코붕|초코봉|초콜릿|초코)',
    '(?<redbean>팥붕|팥봉|팟붕|팟봉|밭붕|단팥|팥소|팥|팟|밭)',
    '(?<cream>슈붕|슈봉|수붕|수봉|쓔붕|슈뿡|슈크림|슈크린|슈그림|수크림|쓔크림|커스터드|크림|슈)',
    '(?<digits>\\d+)',
    '(?<tens>열|스물)\\s*(?<ones>하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉)?',
    '(?<word>하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉)',
    '(?<short>한|두|세|네|석|넉|일|이|삼|사|오|육|칠|팔|구|십)(?=\\s*(?:개|마리))',
  ].join('|'),
  'g',
)

const FLAVOR_GROUPS: readonly Flavor[] = ['choco', 'redbean', 'cream']

function toToken(groups: Record<string, string | undefined>): Token | null {
  const flavor = FLAVOR_GROUPS.find((f) => groups[f])
  if (flavor) return { kind: 'flavor', flavor }
  if (groups.digits) return { kind: 'count', value: Number(groups.digits) }
  if (groups.tens) return { kind: 'count', value: (groups.tens === '열' ? 10 : 20) + (WORD_COUNTS[groups.ones ?? ''] ?? 0) }
  const word = groups.word ?? groups.short
  return word ? { kind: 'count', value: WORD_COUNTS[word] } : null
}

type Spot = { token: Token; raw: string; start: number }

function scan(text: string): Spot[] {
  return [...text.matchAll(TOKEN)].flatMap((m) => {
    const token = toToken(m.groups ?? {})
    return token ? [{ token, raw: m[0].trim(), start: m.index ?? 0 }] : []
  })
}

type Repair = { text: string; guessed: Guess[]; /** where each guessed name now starts in `text` */ at: number[] }

/**
 * A count with no flavor before it ("송 하나") means the word in front of it was meant as a flavor but misheard.
 * Such a word is replaced by the menu name it sounds most like. Nothing else is guessed: filler words and
 * sentences without a count are left alone.
 */
function repair(text: string): Repair {
  const spots = scan(text)
  const found = spots.flatMap((spot, i) => {
    const before = spots[i - 1]
    if (spot.token.kind !== 'count' || before?.token.kind === 'flavor') return []
    const from = before ? before.start + before.raw.length : 0
    const word = /(\S+)\s*$/.exec(text.slice(from, spot.start))
    const flavor = word ? closestFlavor(word[1]) : null
    return word && flavor ? [{ start: from + (word.index ?? 0), heard: word[1], flavor }] : []
  })
  let shift = 0
  const at = found.map((g) => {
    const position = g.start + shift
    shift += menuItem(g.flavor).name.length - g.heard.length
    return position
  })
  const fixed = [...found].reverse().reduce((t, g) => t.slice(0, g.start) + menuItem(g.flavor).name + t.slice(g.start + g.heard.length), text)
  return { text: fixed, guessed: found.map(({ heard, flavor }) => ({ heard, flavor })), at }
}

// Words that take a flavor out of the order. 안 counts only before a verb (안 먹, 안 줘 ...), never inside 안녕 or 안에;
// 됐고 counts, but not 됐어요, which is also how "is it done?" sounds.
const NEGATION = /빼|말고|없이|필요\s*없|제외|싫|됐고|안\s*(?:필요|먹|줘|주|받|넣|원|할)/

type LeftOut = {
  kept: Spot[]
  removed: Flavor[]
  negated: Set<Spot>
  droppedCounts: Set<Spot>
  /** the spoken words that did it ("빼고"), with where they start */
  words: { start: number; text: string }[]
}

/**
 * A flavor followed by "빼고", "말고", "없이" ... is taken out together with the count that belongs to it:
 * "슈크림은 빼고 팥 둘" orders only 팥 2. The words after a flavor, up to the next flavor, are what counts.
 */
function leaveOut(text: string, spots: readonly Spot[]): LeftOut {
  const countBefore = spots[0]?.token.kind === 'count'
  const out: LeftOut = { kept: [], removed: [], negated: new Set(), droppedCounts: new Set(), words: [] }
  spots.forEach((spot, i) => {
    if (spot.token.kind !== 'flavor') return
    const next = spots.findIndex((s, j) => j > i && s.token.kind === 'flavor')
    const from = spot.start + spot.raw.length
    const segment = text.slice(from, next === -1 ? text.length : spots[next].start)
    const hit = NEGATION.exec(segment)
    if (!hit) return
    out.negated.add(spot)
    if (!out.removed.includes(spot.token.flavor)) out.removed.push(spot.token.flavor)
    const wordStart = segment.slice(0, hit.index).search(/\S*$/)
    const wordEnd = hit.index + segment.slice(hit.index).search(/\s|$/)
    out.words.push({ start: from + wordStart, text: segment.slice(wordStart, wordEnd) })
    const counts = countBefore ? [spots[i - 1]] : spots.slice(i + 1, next === -1 ? spots.length : next)
    counts.filter((c) => c?.token.kind === 'count').forEach((c) => out.droppedCounts.add(c))
  })
  out.kept = spots.filter((spot) => !out.negated.has(spot) && !out.droppedCounts.has(spot))
  return out
}

export type VoiceExplain = {
  /** Each spoken word that was read as a flavor or a count, with what it was read as. */
  matched: { text: string; meaning: string }[]
  /** Spoken words that were not used: a misheard flavor shows up here. */
  ignored: string[]
}

// counters and particles that are not worth listing as unused words
const FILLER = ['개', '마리', '은', '는', '이', '가', '을', '를', '도', '랑', '하고', '이랑']

/** For the on-screen recognition log: shows how a heard sentence was read, so a misheard word is easy to spot. */
export function explainVoiceOrder(original: string): VoiceExplain {
  const { text, guessed, at } = repair(original)
  const spots = scan(text)
  const out = leaveOut(text, spots)
  const describe = (spot: Spot) => {
    const { token, raw } = spot
    if (token.kind === 'count') return { text: raw, meaning: out.droppedCounts.has(spot) ? `${token.value} (뺌)` : String(token.value) }
    const name = menuItem(token.flavor).name
    if (out.negated.has(spot)) return { text: raw, meaning: `${name} (뺌)` }
    const guess = guessed[at.indexOf(spot.start)]
    return guess ? { text: guess.heard, meaning: `${name} (추정)` } : { text: raw, meaning: name }
  }
  const entries = [
    ...spots.map((spot) => ({ start: spot.start, length: spot.raw.length, ...describe(spot) })),
    ...out.words.map((w) => ({ start: w.start, length: w.text.length, text: w.text, meaning: '빼기' })),
  ].sort((a, b) => a.start - b.start)
  const rest = entries.reduce((left, { start, length }) => left.slice(0, start) + ' '.repeat(length) + left.slice(start + length), text)
  const ignored = rest.split(/\s+/).filter((word) => word !== '' && !FILLER.includes(word))
  return { matched: entries.map(({ text: said, meaning }) => ({ text: said, meaning })), ignored }
}

/** "팥붕 두 개" counts after the flavor; a sentence that starts with a number ("두 개 팥붕") counts before it. */
function wantedFlavors(tokens: readonly Token[]): [Flavor, number][] {
  const countBefore = tokens[0]?.kind === 'count'
  const wanted: [Flavor, number][] = []
  for (let i = 0; i < tokens.length; i += 1) {
    const here = tokens[i]
    const next = tokens[i + 1]
    if (countBefore && here.kind === 'count' && next?.kind === 'flavor') {
      wanted.push([next.flavor, here.value])
      i += 1
    } else if (!countBefore && here.kind === 'flavor') {
      const counted = next?.kind === 'count'
      wanted.push([here.flavor, counted ? next.value : 1])
      if (counted) i += 1
    } else if (here.kind === 'flavor') {
      wanted.push([here.flavor, 1])
    }
  }
  return wanted
}

export function parseVoiceOrder(original: string, canOrder: (flavor: Flavor) => boolean): VoiceResult {
  const { text, guessed } = repair(original)
  const { kept, removed } = leaveOut(text, scan(text))
  const unavailable: Flavor[] = []
  let cart: Cart = {}
  let clipped = false
  for (const [flavor, qty] of wantedFlavors(kept.map((spot) => spot.token))) {
    if (!canOrder(flavor)) {
      if (!unavailable.includes(flavor)) unavailable.push(flavor)
      continue
    }
    for (let added = 0; added < qty; added += 1) {
      const next = addToCart(cart, flavor)
      if (next === cart) {
        clipped = true
        break
      }
      cart = next
    }
  }
  return { cart, unavailable, clipped, guessed, removed }
}
