import type { Flavor } from './menu'

/**
 * Which flavor does a misheard word most sound like? Syllables are compared by their parts (first consonant,
 * vowel, last consonant), where sounds that speech recognition mixes up count as the same:
 * 송 ~ 슈, 분 ~ 붕, 파 ~ 팥. This only runs for a word that stands where a flavor should be.
 */

const BASE = 0xac00
const LAST = 0xd7a3
const INITIALS = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
const MEDIALS = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
const FINALS = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

// plain / tense / aspirated versions of one consonant sound
const INITIAL_SAME: Record<string, string> = { ㄲ: 'ㄱ', ㅋ: 'ㄱ', ㄸ: 'ㄷ', ㅌ: 'ㄷ', ㅃ: 'ㅂ', ㅍ: 'ㅂ', ㅆ: 'ㅅ', ㅉ: 'ㅈ', ㅊ: 'ㅈ' }

const MEDIAL_SAME: Record<string, string> = {
  ㅗ: 'O', ㅛ: 'O', ㅜ: 'O', ㅠ: 'O', ㅘ: 'O', ㅝ: 'O',
  ㅏ: 'A', ㅑ: 'A', ㅓ: 'EO', ㅕ: 'EO', ㅐ: 'E', ㅔ: 'E', ㅒ: 'E', ㅖ: 'E',
}

// a last consonant is heard as one of a few sounds: nasal, or a stop made at the throat, tongue or lips
const FINAL_SAME: Record<string, string> = {
  ㄴ: 'N', ㅁ: 'N', ㅇ: 'N', ㄵ: 'N', ㄶ: 'N', ㄻ: 'N',
  ㄱ: 'K', ㄲ: 'K', ㅋ: 'K', ㄳ: 'K', ㄺ: 'K',
  ㄷ: 'T', ㅅ: 'T', ㅆ: 'T', ㅈ: 'T', ㅊ: 'T', ㅌ: 'T', ㅎ: 'T', ㅀ: 'T',
  ㅂ: 'P', ㅍ: 'P', ㅄ: 'P', ㄼ: 'P', ㄿ: 'P',
  ㄹ: 'L', ㄽ: 'L', ㄾ: 'L',
}

type Parts = { initial: string; medial: string; final: string }

function partsOf(syllable: string): Parts {
  const offset = syllable.charCodeAt(0) - BASE
  const initial = INITIALS[Math.floor(offset / 588)]
  const medial = MEDIALS[Math.floor((offset % 588) / 28)]
  const final = FINALS[offset % 28]
  return { initial: INITIAL_SAME[initial] ?? initial, medial: MEDIAL_SAME[medial] ?? medial, final: FINAL_SAME[final] ?? final }
}

/** 0..1: how alike two syllables sound. The first consonant and the vowel count most. */
function syllableSimilarity(a: string, b: string): number {
  const x = partsOf(a)
  const y = partsOf(b)
  return (x.initial === y.initial ? 0.4 : 0) + (x.medial === y.medial ? 0.4 : 0) + (x.final === y.final ? 0.2 : 0)
}

const mean = (values: readonly number[]) => values.reduce((sum, v) => sum + v, 0) / values.length

// Every syllable must at least half match: one close syllable does not make 성분 sound like 슈붕 just because 분 ~ 붕.
const MIN_SYLLABLE = 0.5

/** Average similarity of aligned syllables, or 0 when any one of them sounds like something else. */
function aligned(spoken: readonly string[], target: readonly string[]): number {
  const each = spoken.map((s, i) => syllableSimilarity(s, target[i]))
  return Math.min(...each) >= MIN_SYLLABLE ? mean(each) : 0
}

/**
 * How alike a heard word and a menu name sound. A shorter word may match the start of the name, or less well its
 * end (the recognizer often drops a syllable); a longer one is compared with the name's length only.
 */
function similarity(word: string, name: string): number {
  const spoken = [...word]
  const target = [...name]
  if (spoken.length > target.length) return 0.8 * aligned(spoken.slice(0, target.length), target)
  const fits = Array.from({ length: target.length - spoken.length + 1 }, (_, offset) => {
    const alike = aligned(spoken, target.slice(offset, offset + spoken.length))
    return offset === 0 ? alike : alike * 0.7
  })
  return Math.max(...fits) * (0.75 + (0.25 * spoken.length) / target.length)
}

// Menu names a word is compared with (two syllables or more, so one stray sound cannot match).
const SOUNDS: Record<Flavor, readonly string[]> = {
  cream: ['슈붕', '슈크림', '수붕'],
  redbean: ['팥붕', '단팥', '팟붕'],
  choco: ['초코붕'],
}

const MIN_SCORE = 0.6
const MIN_LEAD = 0.15
const MAX_SYLLABLES = 4

/** The flavor a heard word most sounds like, or null when it sounds like nothing in particular or like two at once. */
export function closestFlavor(word: string): Flavor | null {
  if (!new RegExp(`^[\\uac00-\\ud7a3]{1,${MAX_SYLLABLES}}$`).test(word) || [...word].some((c) => c.charCodeAt(0) > LAST)) return null
  const scored = (Object.keys(SOUNDS) as Flavor[])
    .map((flavor) => ({ flavor, score: Math.max(...SOUNDS[flavor].map((name) => similarity(word, name))) }))
    .sort((a, b) => b.score - a.score)
  const [best, second] = scored
  return best.score >= MIN_SCORE && best.score - (second?.score ?? 0) >= MIN_LEAD ? best.flavor : null
}
