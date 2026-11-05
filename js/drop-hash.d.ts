// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
export type ListType = 'email' | 'phone' | 'ndz';
export type StatusCode = 2 | 3 | 4 | 5;
export interface ConsumerRecord {
  first_name?: string | null; last_name?: string | null; dob?: string | null;
  zip?: string | null; phone?: string | null; email?: string | null;
}
export const STATUS: Record<StatusCode, 'exempt' | 'deleted' | 'opted_out' | 'not_found'>;
export const LIST_TYPES: ListType[];
export const RESPONSE_WINDOW_DAYS: 45;
export const TRANSLIT: Record<string, string>;
export function stdName(v: string | null | undefined): string | null;
export function stdEmail(v: string | null | undefined): string | null;
export function stdPhone(v: string | null | undefined): string | null;
export function stdZip(v: string | null | undefined): string | null;
export function stdDob(v: string | null | undefined): string | null;
export const STANDARDIZERS: Record<'first_name' | 'last_name' | 'dob' | 'zip' | 'phone' | 'email', (v: string | null | undefined) => string | null>;
export function hashValue(s: string): Promise<string>;
export function sha256Hex(text: string): Promise<string>;
export function compositeHash(fieldHashes: string[]): Promise<string>;
export function hashFor(listType: ListType, rec: ConsumerRecord): Promise<string | null>;
