# BabyCare — Demo Script (Premature Infants)

Questions a parent of a premature baby commonly asks, each with the scientific
answer, its references, and the last-30-second vital line the app prints.

All clinical figures below are sourced. The vital line uses your
Reference_Values.xlsx (Fleming 2011 centiles), shown as term reference points —
the corrected-age answer explains why that matters for a preemie.

**Demo setup:** in `babycare_demo.py`, keep `DEMO_AGE_DAYS` at a small value
(e.g. 30) so the vital line reads against an early bracket. Simulated means sit
inside the band so the line prints green; nudge `read_last_30s()` upward to show
a red out-of-range line.

---

## 1. "What are these apnea and bradycardia 'spells' the nurses keep talking about?"

**Answer that prints:**

Apnea of prematurity is one of the most common conditions in the NICU. It means
a pause in breathing longer than about 20 seconds — or a shorter pause paired
with a drop in heart rate (bradycardia, below 100 beats/min) or oxygen level
(desaturation, below about 85%). It happens because a premature baby's brain and
breathing-control systems are still immature, not because anything is
fundamentally wrong with the lungs. It's usually monitored continuously in the
NICU, often treated with caffeine to stimulate breathing, and typically resolves
on its own as the baby matures — a common benchmark is 5–7 days free of events.

**References:**
- Eichenwald EC; AAP Committee on Fetus and Newborn. Apnea of Prematurity.
  Pediatrics. 2016;137(1):e20153757.
- Apnea of Prematurity. Merck Manual, Professional Edition, 2025.
- Apnea of Prematurity. Nemours KidsHealth (parent guidance).

**Vital line (last 30 s):** heart rate + typical range for the age bracket.

---

## 2. "My baby is 10 weeks old but doesn't do what other 10-week-olds do. Is something wrong?"

**Answer that prints:**

For a premature baby, use *corrected age* rather than age since birth for the
first two years. Take the baby's age in weeks since birth and subtract the number
of weeks born early (40 weeks minus gestational age at birth). For example, a
baby born at 32 weeks is 8 weeks early; at 16 weeks old, the corrected age is
8 weeks. You'd expect the developmental skills of a 2-month-old, not a
4-month-old. This is the standard the American Academy of Pediatrics recommends,
and most preemies catch up to their term peers by about age 2.

**References:**
- American Academy of Pediatrics. Corrected Age for Preemies. HealthyChildren.org.
- AAP. Your Preemie's Growth: Developmental Milestones (patient education).

**Vital line (last 30 s):** shown, with note that term reference ranges are best
read against corrected age.

---

## 3. "Is my baby breathing normally right now?"

**Answer that prints:**

Newborns typically breathe 30–60 times a minute, and irregular breathing with
brief pauses is common. In a premature baby, though, a pause beyond about
20 seconds — or a shorter pause with a heart-rate or oxygen drop — is defined as
apnea of prematurity and is monitored closely. The distinction that matters is
between normal periodic breathing and a true apnea spell, which is why continuous
monitoring is used in and sometimes after the NICU. Persistent fast breathing
above 60/min, nostril flaring, chest pulling-in, grunting, or any bluish colour
needs prompt attention.

**References:**
- Fleming S, et al. Lancet. 2011;377(9770):1011-1018 (respiratory rate centiles).
- Eichenwald EC; AAP. Apnea of Prematurity. Pediatrics. 2016;137(1):e20153757.

**Vital line (last 30 s):** breathing rate + typical range for the bracket.

---

## 4. "Her hands and feet look a little blue, how is she? I don't understand these numbers on screen; is my baby okay?"

**Answer that prints:**

First, the quick answer. Blue hands and feet on their own are usually the ordinary kind of blue. Look at her tongue and her lips instead. If those are pink, she is getting the oxygen she needs.

Blue that stays out at the hands and feet has a name, acrocyanosis. The tiny vessels at a newborn's edges tighten easily, so blood moves through her fingers and toes slowly and gives up more of its oxygen on the way. You will see it most when she is cold, when she has just been unwrapped, or after a hard cry. It fades as she warms. Blue on the tongue, lips, or face is a different thing. That one is never normal in a newborn, and it needs a nurse right away.

Here is why the numbers matter more than the color. Skin does not start to look blue until about 15 percent of the oxygen is already gone, and it is easy to miss in warm lighting or on darker skin. The monitor sees it before your eyes can.

Now, the three numbers on the left of the screen.

Heart rate, in beats per minute. It climbs when she cries or feeds and settles when she sleeps, so a number that moves around is a good sign. With a premature baby, the low end is what the nurses watch. A sustained drop under 100 is called a bradycardia.

Breathing rate, in breaths per minute. Newborn breathing comes in clusters with short gaps in between, and that irregular rhythm is normal. A gap longer than about 20 seconds, or a shorter gap that comes with a heart rate or oxygen drop, is an apnea spell.

Oxygen saturation, the percent of her blood currently carrying oxygen. A healthy full-term baby breathing room air sits at 95 or above, most often 97 to 99. A premature baby on extra oxygen is often kept a little lower on purpose, somewhere around 90 to 95, because too much oxygen is hard on premature eyes and lungs. Below about 85 is called a desaturation.

One thing to know about this particular reading. A sensor sitting on a cold, blue, sluggish hand or foot can read low even when she is fine. If the number looks low but her tongue is pink and she is breathing comfortably, warm that hand, wait a minute, and look again before you worry.

Call a nurse now if the blue reaches her tongue, lips, or face, if it does not clear once she warms up, if a low number comes along with a breathing pause or floppiness or poor feeding, or if she is grunting, flaring her nostrils, or pulling in at the ribs.

References:

Fouzas S, Priftis KN, Anthracopoulos MB. Pulse Oximetry in Pediatric Practice. Pediatrics. 2011;128(4):740-752.
Gomella TL, et al. Neonatology, 8e. Cyanosis: peripheral versus central, and falsely low SpO₂ from a cold extremity.
Cyanosis. StatPearls, NCBI Bookshelf, 2022. Visible cyanosis at 5 g/dL deoxyhemoglobin.
Fleming S, et al. Lancet. 2011;377(9770):1011-1018. Heart rate and respiratory rate centiles.
NICU Oxygen Saturation Targets for Preterm Infants, Johns Hopkins All Children's clinical pathway, 2023. The 90 to 95 percent preterm target.
Apnea of Prematurity. Merck Manual, Professional Edition, 2025. Desaturation below 85 percent.
Cyanosis. Cincinnati Children's. Parent-facing framing, nail beds and lips and tongue.

**Vital line (last few minutes):** SpO₂ + HR + RR trend (not SpO₂ alone).

---

## 5. "Does holding my baby skin-to-skin actually help, or is it just nice?"

**Answer that prints:**

It genuinely helps. Skin-to-skin ("kangaroo") care has been associated with fewer
apnea and bradycardia episodes in premature babies, alongside more stable
temperature and better feeding. A stable thermal environment and developmental
care — nesting, gentle handling, clustering of care to allow rest — are part of
the same picture. It is one of the few things a parent can do directly at the
bedside that supports the baby's stability.

**References:**
- The A, B, Ds of NICU Life: Apnea of Prematurity. Canadian Premature Babies
  Foundation, 2024 (kangaroo care and developmental care).
- Eichenwald EC; AAP. Apnea of Prematurity. Pediatrics. 2016;137(1):e20153757.

**Vital line (last 30 s):** heart rate + typical range (nice to show it steady).

---

## 6. "When can my baby come home — what has to happen first?"

**Answer that prints:**

Most NICUs look for a stretch of stability rather than a fixed date. A common
benchmark is 5–7 days with no clinically significant apnea, bradycardia, or
desaturation spells — one study of infants born at 34 weeks or earlier found a
5–7 day event-free period predicted resolution in 94–96% of cases. Before
discharge, preterm babies also typically pass a "car seat challenge" (monitored
in their car seat to check for pauses or drops), feed reliably, and maintain
temperature in an open crib. Only a small number go home on a monitor.

**References:**
- Chandrasekharan P, et al. Apnea, bradycardia and desaturation spells in
  premature infants. (NICU spell-free observation protocol.)
- Apnea of Prematurity. Merck Manual, Professional Edition, 2025 (car seat
  challenge; discharge criteria).

**Vital line (last 30 s):** heart rate + typical range.

---

## Notes for filming

- The four topics already coded in the app (heart rate, breathing, fever, safe
  sleep) still work. Questions 1, 5, and 6 above are new preemie topics — say
  the word and I'll add them as coded presets so typing them triggers a real
  answer + vital line instead of the fallback.
- Every number above is traceable to a named source. If the camera lingers on a
  figure, it will hold up.
- Honest framing preserved from your spreadsheet: the vital ranges describe
  healthy-term physiology at rest and are reference ranges, not alarm limits —
  the app already prints that caveat under the bolded line.

## NeoTex Signal View (booth chat)

The PyQt belt receiver keeps **live vitals on the left** and swaps the main pane
between **Signal streams** and **Nurse chat**:

- Hamburger → **Signal view** / **Nurse chat**
- Header **Ask nurse** (or chat submit / demo chip) opens the chat pane
- Chat **← Signals** returns to waveforms

Preferred demo ask:

> Her hands and feet look a little blue, how is she? I don't understand these
> numbers; oxygen level is okay?

Replies follow the templates above and append a vital line from the last ~3
minutes of streamed metrics.
