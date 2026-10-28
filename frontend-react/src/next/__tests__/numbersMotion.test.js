import { act, renderHook } from '@testing-library/react'
import { createElement } from 'react'
import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import useFoldLayout from '../numbers/useFoldLayout.js'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const here = import.meta.url
const sheetStyles = readFileSync(fileURLToPath(new URL('../numbers/numbersSheet.css', here)), 'utf8')
const rows=[{key:'bankActiveLoans'}]
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals()})
test('promotion grows the row during the entry fade, without a mount animation',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {result,rerender}=renderHook(({keys})=>useFoldLayout(rows,keys),{initialProps:{keys:['bankActiveLoans']}})
 expect(result.current.bankActiveLoans.phase).toBe('folded')
 expect(result.current.bankActiveLoans.promoted).toBeFalsy()
 expect(result.current.bankActiveLoans.leavingEntry).toBeFalsy()
 expect(vi.getTimerCount()).toBe(0)
 rerender({keys:[]});expect(result.current.bankActiveLoans.phase).toBe('entering-row')
 expect(result.current.bankActiveLoans.leavingEntry).toBe(true)
 expect(result.current.bankActiveLoans.promoted).toBe(true)
 act(()=>vi.advanceTimersByTime(160));expect(result.current.bankActiveLoans.phase).toBe('entering-row')
 expect(result.current.bankActiveLoans.leavingEntry).toBe(false)
 act(()=>vi.advanceTimersByTime(259));expect(result.current.bankActiveLoans.phase).toBe('entering-row')
 act(()=>vi.advanceTimersByTime(1));expect(result.current.bankActiveLoans.phase).toBe('row')
 rerender({keys:['bankActiveLoans']});expect(result.current.bankActiveLoans.phase).toBe('leaving-row')
 act(()=>vi.advanceTimersByTime(420));expect(result.current.bankActiveLoans.phase).toBe('entering-entry')
 act(()=>vi.advanceTimersByTime(160));expect(result.current.bankActiveLoans.phase).toBe('folded')
})
test('reduced motion snaps membership changes without timers',()=>{
 vi.useFakeTimers()
 vi.stubGlobal('matchMedia',()=>({matches:true}))
 const {result,rerender}=renderHook(({keys})=>useFoldLayout(rows,keys),{initialProps:{keys:[]}})
 expect(result.current.bankActiveLoans.phase).toBe('row')
 rerender({keys:['bankActiveLoans']});expect(result.current.bankActiveLoans.phase).toBe('folded')
 rerender({keys:[]});expect(result.current.bankActiveLoans.phase).toBe('row')
 expect(result.current.bankActiveLoans.leavingEntry).toBeFalsy()
 expect(vi.getTimerCount()).toBe(0)
})

test('a row already showing on mount has no growth timer or promotion flash',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {result}=renderHook(()=>useFoldLayout(rows,[]))
 expect(result.current.bankActiveLoans.phase).toBe('row')
 expect(result.current.bankActiveLoans.promoted).toBeFalsy()
 expect(result.current.bankActiveLoans.leavingEntry).toBeFalsy()
 expect(vi.getTimerCount()).toBe(0)
})

test('tick rerenders and entry cleanup do not restart the 420ms growth deadline',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {result,rerender}=renderHook(({keys})=>useFoldLayout(rows,keys),{initialProps:{keys:['bankActiveLoans']}})
 rerender({keys:[]})
 for(let elapsed=40;elapsed<=400;elapsed+=40) {
  act(()=>vi.advanceTimersByTime(40));rerender({keys:[]})
  expect(result.current.bankActiveLoans.phase).toBe('entering-row')
  expect(result.current.bankActiveLoans.leavingEntry).toBe(elapsed<160)
 }
 act(()=>vi.advanceTimersByTime(20))
 expect(result.current.bankActiveLoans.phase).toBe('row')
})

// Exercise the hook against the sheet's real CSS. JSDOM exposes style targets,
// not interpolated pixels: these checks guard against a full-height keyframe
// restart and leave interpolation/reversal to the browser's CSS transitions.
function MotionRow({ folded }) {
 const layout=useFoldLayout(rows,folded?['bankActiveLoans']:[])
 return createElement('div',{className:'nx'},
  createElement('style',null,sheetStyles),
  createElement('div',{className:'nx-row-motion','data-state':layout.bankActiveLoans.phase,'data-testid':'moving-row'},
   createElement('div',{className:'nx-row-motion-inner'},'Bank loans')))
}

test('reversing during the entry fade retargets the existing row transition',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {rerender,getByTestId}=render(createElement(MotionRow,{folded:true}))
 const row=getByTestId('moving-row')
 expect(getComputedStyle(row).visibility).toBe('hidden')
 rerender(createElement(MotionRow,{folded:false}))
 act(()=>vi.advanceTimersByTime(80))
 const growing=getComputedStyle(row)
 expect(growing.gridTemplateRows).toBe('1fr')
 expect(growing.opacity).toBe('1')
 expect(growing.visibility).not.toBe('hidden')
 rerender(createElement(MotionRow,{folded:true}))
 const reversing=getComputedStyle(row)
 expect(reversing.gridTemplateRows).toBe('0fr')
 expect(reversing.transition).toBe(growing.transition)
 expect(reversing.visibility).not.toBe('hidden')
 expect(reversing.animation).toBe('')
 act(()=>vi.advanceTimersByTime(420))
 expect(getComputedStyle(row).visibility).toBe('hidden')
})

test('reversing a growing row keeps the same height transition instead of restarting at full height',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {rerender,getByTestId}=render(createElement(MotionRow,{folded:true}))
 const row=getByTestId('moving-row')
 rerender(createElement(MotionRow,{folded:false}))
 act(()=>vi.advanceTimersByTime(160))
 act(()=>vi.advanceTimersByTime(120))
 const growing=getComputedStyle(row)
 expect(growing.gridTemplateRows).toBe('1fr')
 expect(growing.transition).toContain('grid-template-rows var(--nx-change) var(--nx-ease)')
 expect(growing.animation).toBe('')
 rerender(createElement(MotionRow,{folded:true}))
 const reversing=getComputedStyle(row)
 expect(reversing.gridTemplateRows).toBe('0fr')
 expect(reversing.transition).toBe(growing.transition)
 expect(reversing.animation).toBe('')
 act(()=>vi.advanceTimersByTime(420))
 expect(getComputedStyle(row).gridTemplateRows).toBe('0fr')
})
