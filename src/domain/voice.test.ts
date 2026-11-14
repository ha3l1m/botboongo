import { describe, expect, it } from 'vitest'
import { explainVoiceOrder, parseVoiceOrder } from './voice'

const all = () => true
const noChoco = (flavor: string) => flavor !== 'choco'

describe('parseVoiceOrder', () => {
  it('reads native Korean counts after each flavor', () => {
    expect(parseVoiceOrder('팥붕 두 개 슈붕 하나', all).cart).toEqual({ redbean: 2, cream: 1 })
  })

  it('does not take the 세 of 주세요 for a count of three', () => {
    expect(parseVoiceOrder('팥붕 두개랑 슈붕 세 개 주세요', all).cart).toEqual({ redbean: 2, cream: 3 })
    expect(parseVoiceOrder('슈붕 주세요', all).cart).toEqual({ cream: 1 })
  })

  it('reads digits, sino counts with a counter, and flavor nicknames', () => {
    expect(parseVoiceOrder('팥붕 2개 슈크림 1개', all).cart).toEqual({ redbean: 2, cream: 1 })
    expect(parseVoiceOrder('단팥 삼 마리', all).cart).toEqual({ redbean: 3 })
    expect(parseVoiceOrder('열 마리 슈크림', all).cart).toEqual({ cream: 10 })
  })

  it('orders one when no count is spoken and adds repeated flavors together', () => {
    expect(parseVoiceOrder('팥붕', all).cart).toEqual({ redbean: 1 })
    expect(parseVoiceOrder('팥붕 하나 슈붕 팥붕 둘', all).cart).toEqual({ redbean: 3, cream: 1 })
  })

  it('reads the count before the flavor when the sentence starts with a number', () => {
    expect(parseVoiceOrder('두 개 팥붕 한 개 슈붕', all).cart).toEqual({ redbean: 2, cream: 1 })
  })

  it('keeps unavailable flavors out of the cart and reports them', () => {
    const result = parseVoiceOrder('팥붕 하나 초코붕 두 개', noChoco)
    expect(result.cart).toEqual({ redbean: 1 })
    expect(result.unavailable).toEqual(['choco'])
  })

  it('cuts to the menu limits and says so', () => {
    const per = parseVoiceOrder('팥붕 25개', all)
    expect(per.cart).toEqual({ redbean: 10 })
    expect(per.clipped).toBe(true)
    const total = parseVoiceOrder('팥붕 열 마리 슈붕 열 마리 초코붕 한 마리', all)
    expect(total.cart).toEqual({ redbean: 10, cream: 10 })
    expect(total.clipped).toBe(true)
    expect(parseVoiceOrder('팥붕 두 개', all).clipped).toBe(false)
  })

  it('returns an empty order when nothing is recognized', () => {
    expect(parseVoiceOrder('안녕하세요', all)).toEqual({ cart: {}, unavailable: [], clipped: false, guessed: [], removed: [] })
    expect(parseVoiceOrder('', all).cart).toEqual({})
  })
})

describe('explainVoiceOrder', () => {
  it('shows which spoken words were read as a flavor or a count', () => {
    expect(explainVoiceOrder('팥붕 두 개 슈붕 하나')).toEqual({
      matched: [
        { text: '팥붕', meaning: '팥붕' },
        { text: '두', meaning: '2' },
        { text: '슈붕', meaning: '슈붕' },
        { text: '하나', meaning: '1' },
      ],
      ignored: [],
    })
  })

  it('shows nicknames mapped to the menu name', () => {
    expect(explainVoiceOrder('단팥 3개').matched).toEqual([
      { text: '단팥', meaning: '팥붕' },
      { text: '3', meaning: '3' },
    ])
  })

  it('lists the words it did not use, so a misheard word is easy to spot', () => {
    expect(explainVoiceOrder('저기 두 개 주세요')).toEqual({ matched: [{ text: '두', meaning: '2' }], ignored: ['저기', '주세요'] })
    // 팥 alone is a nickname, so a slightly misheard 팥분 still counts and only the stray 분 is left over
    expect(explainVoiceOrder('팥분 하나')).toEqual({ matched: [{ text: '팥', meaning: '팥붕' }, { text: '하나', meaning: '1' }], ignored: ['분'] })
    expect(explainVoiceOrder('안녕하세요')).toEqual({ matched: [], ignored: ['안녕하세요'] })
    expect(explainVoiceOrder('')).toEqual({ matched: [], ignored: [] })
  })
})

describe('words that sound like a flavor', () => {
  it('reads a misheard word right before a count as the closest flavor, and says it guessed', () => {
    const result = parseVoiceOrder('송하나', all)
    expect(result.cart).toEqual({ cream: 1 })
    expect(result.guessed).toEqual([{ heard: '송', flavor: 'cream' }])
  })

  it.each([
    ['파붕 두 개', { redbean: 2 }],
    ['슈분 하나', { cream: 1 }],
    ['송붕 세 개', { cream: 3 }],
    ['팥붕 하나 송 하나', { redbean: 1, cream: 1 }],
  ])('guesses %s', (text, cart) => {
    expect(parseVoiceOrder(text, all).cart).toEqual(cart)
  })

  it('does not guess for filler or unrelated words, so ordinary speech never becomes an order', () => {
    // 수박, 승부, 성분 each have one syllable close to a menu name and another that is not: no guess
    for (const text of ['저기 하나', '이거 하나', '음 하나', '그럼 두 개', '똥 하나', '주세요 하나', '안녕하세요', '하나', '수박 하나', '승부 하나', '성분 하나']) {
      expect(parseVoiceOrder(text, all)).toEqual({ cart: {}, unavailable: [], clipped: false, guessed: [], removed: [] })
    }
  })

  it('does not guess when the count already has its flavor, and keeps exact words exact', () => {
    expect(parseVoiceOrder('팥분 하나', all)).toEqual({ cart: { redbean: 1 }, unavailable: [], clipped: false, guessed: [], removed: [] })
    expect(parseVoiceOrder('팥붕 두 개 슈붕 하나', all).guessed).toEqual([])
  })

  it('still reports an unavailable flavor that was only guessed', () => {
    const result = parseVoiceOrder('초코붕 두 개', noChoco)
    expect(result.unavailable).toEqual(['choco'])
    expect(result.guessed).toEqual([])
  })

  it('knows more spellings of the same flavor', () => {
    expect(parseVoiceOrder('수크림 두 개', all).cart).toEqual({ cream: 2 })
    expect(parseVoiceOrder('커스터드 하나', all).cart).toEqual({ cream: 1 })
    expect(parseVoiceOrder('크림 두 개', all).cart).toEqual({ cream: 2 })
    expect(parseVoiceOrder('팟붕 하나', all).cart).toEqual({ redbean: 1 })
    expect(parseVoiceOrder('밭붕 두 개', all).cart).toEqual({ redbean: 2 })
    expect(parseVoiceOrder('팟 둘', all).cart).toEqual({ redbean: 2 })
  })

  it('shows a guess in the explanation, marked as a guess', () => {
    expect(explainVoiceOrder('송하나')).toEqual({
      matched: [
        { text: '송', meaning: '슈붕 (추정)' },
        { text: '하나', meaning: '1' },
      ],
      ignored: [],
    })
  })
})

describe('leaving a flavor out', () => {
  it('drops a flavor the customer said to leave out, and orders the rest', () => {
    const result = parseVoiceOrder('슈크림은 빼고 팥 둘', all)
    expect(result.cart).toEqual({ redbean: 2 })
    expect(result.removed).toEqual(['cream'])
  })

  it.each([
    ['팥 말고 슈크림 둘', { cream: 2 }, ['redbean']],
    ['슈붕 하나 빼고 팥붕 둘', { redbean: 2 }, ['cream']],
    ['팥붕 하나 슈붕은 빼고', { redbean: 1 }, ['cream']],
    ['슈크림 없이 팥 세 개', { redbean: 3 }, ['cream']],
    ['초코 제외하고 팥 하나', { redbean: 1 }, ['choco']],
    ['슈크림은 싫어요 팥 하나', { redbean: 1 }, ['cream']],
    ['슈크림빼고 팥 둘', { redbean: 2 }, ['cream']],
    ['두 개 슈붕 빼고 한 개 팥붕', { redbean: 1 }, ['cream']],
    ['슈크림 빼고', {}, ['cream']],
    ['슈크림은 안 필요해요 팥 둘', { redbean: 2 }, ['cream']],
    ['슈크림은 안 먹을래요 팥 둘', { redbean: 2 }, ['cream']],
    ['슈크림은 안 줘도 돼요 팥 둘', { redbean: 2 }, ['cream']],
    ['슈크림은 됐고 팥 둘', { redbean: 2 }, ['cream']],
  ])('reads %s', (text, cart, removed) => {
    const result = parseVoiceOrder(text, all)
    expect(result.cart).toEqual(cart)
    expect(result.removed).toEqual(removed)
  })

  it('reads "필요 없어요" as leaving out, but not other words that merely sound alike', () => {
    expect(parseVoiceOrder('팥붕 두 개 주세요 슈붕은 필요 없어요', all)).toMatchObject({ cart: { redbean: 2 }, removed: ['cream'] })
    // 없으면 ("if there is none") is not 없이 ("without")
    expect(parseVoiceOrder('슈붕 하나 없으면 팥붕 하나', all)).toMatchObject({ cart: { cream: 1, redbean: 1 }, removed: [] })
  })

  it('does not take 안녕하세요 or a question like "다 됐어요?" for leaving something out', () => {
    expect(parseVoiceOrder('안녕하세요 팥붕 하나', all)).toMatchObject({ cart: { redbean: 1 }, removed: [] })
    expect(parseVoiceOrder('팥붕 하나 다 됐어요', all)).toMatchObject({ cart: { redbean: 1 }, removed: [] })
    expect(parseVoiceOrder('팥붕 한 판 안에 슈붕 하나', all)).toMatchObject({ cart: { redbean: 1, cream: 1 }, removed: [] })
  })

  it('does not report a left-out flavor as unavailable, and leaves ordinary sentences alone', () => {
    expect(parseVoiceOrder('초코붕 빼고 팥 하나', noChoco).unavailable).toEqual([])
    const plain = parseVoiceOrder('팥붕 두 개 슈붕 하나 주세요', all)
    expect(plain.cart).toEqual({ redbean: 2, cream: 1 })
    expect(plain.removed).toEqual([])
  })

  it('shows the leaving out in the explanation, without listing the words used for it as ignored', () => {
    expect(explainVoiceOrder('슈크림은 빼고 팥 둘')).toEqual({
      matched: [
        { text: '슈크림', meaning: '슈붕 (뺌)' },
        { text: '빼고', meaning: '빼기' },
        { text: '팥', meaning: '팥붕' },
        { text: '둘', meaning: '2' },
      ],
      ignored: [],
    })
    expect(explainVoiceOrder('슈붕 하나 빼고 팥붕 둘').matched).toEqual([
      { text: '슈붕', meaning: '슈붕 (뺌)' },
      { text: '하나', meaning: '1 (뺌)' },
      { text: '빼고', meaning: '빼기' },
      { text: '팥붕', meaning: '팥붕' },
      { text: '둘', meaning: '2' },
    ])
  })
})
