// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
/**
 * MatchWizard — linear 1→2→3→4 entry flow for /match-elements.
 *
 * Design intent: feel like an Apple-team product page — generous
 * whitespace, soft gradients, subtle depth, micro-interactions, a single
 * unmistakable primary CTA. The wizard replaces the previous "everything
 * scattered, settings hidden until after a session is created" layout
 * that Artem reported as "ничего не работает".
 *
 * Flow:
 *   1. Stage      — what phase of work am I matching?
 *   2. Catalogue  — which CWICR rate book?
 *   3. Source     — BIM model / Excel BoQ / pasted text
 *   4. Review     — confirm + Run (creates session + fires vector match)
 *
 * After Run the user is dropped into the existing results UI via the
 * onComplete(sessionId) callback. Resume path: existing sessions are
 * surfaced on Step 1 so power users can skip the wizard entirely.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';