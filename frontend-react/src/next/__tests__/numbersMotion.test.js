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
test('fold motion has ordered entry/row phases, without a mount animation',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {result,rerender}=renderHook(({keys})=>useFoldLayout(rows,keys),{initialProps:{keys:['bankActiveLoans']}})
 expect(result.current.bankActiveLoans.phase).toBe('folded')
 rerender({keys:[]});expect(result.current.bankActiveLoans.phase).toBe('leaving-entry')
 act(()=>vi.advanceTimersByTime(160));expect(result.current.bankActiveLoans.phase).toBe('entering-row')
 act(()=>vi.advanceTimersByTime(420));expect(result.current.bankActiveLoans.phase).toBe('row')
 rerender({keys:['bankActiveLoans']});expect(result.current.bankActiveLoans.phase).toBe('leaving-row')
 act(()=>vi.advanceTimersByTime(420));expect(result.current.bankActiveLoans.phase).toBe('entering-entry')
 act(()=>vi.advanceTimersByTime(160));expect(result.current.bankActiveLoans.phase).toBe('folded')
})
test('reduced motion snaps membership changes without timers',()=>{
 vi.stubGlobal('matchMedia',()=>({matches:true}))
 const {result,rerender}=renderHook(({keys})=>useFoldLayout(rows,keys),{initialProps:{keys:[]}})
 expect(result.current.bankActiveLoans.phase).toBe('row')
 rerender({keys:['bankActiveLoans']});expect(result.current.bankActiveLoans.phase).toBe('folded')
 rerender({keys:[]});expect(result.current.bankActiveLoans.phase).toBe('row')
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

test('reversing during the entry fade never exposes a full-height row',()=>{
 vi.useFakeTimers();vi.stubGlobal('matchMedia',()=>({matches:false}))
 const {rerender,getByTestId}=render(createElement(MotionRow,{folded:true}))
 const row=getByTestId('moving-row')
 const expectHidden=()=>{
  const style=getComputedStyle(row)
  expect(style.gridTemplateRows).toBe('0fr')
  expect(style.opacity).toBe('0')
  expect(style.visibility).toBe('hidden')
  expect(style.animation).not.toContain('shrink')
 }
 expectHidden()
 rerender(createElement(MotionRow,{folded:false}))
 act(()=>vi.advanceTimersByTime(80));expectHidden()
 rerender(createElement(MotionRow,{folded:true}));expectHidden()
 for(const elapsed of [40,40,80,420]) {
  act(()=>vi.advanceTimersByTime(elapsed));expectHidden()
 }
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
