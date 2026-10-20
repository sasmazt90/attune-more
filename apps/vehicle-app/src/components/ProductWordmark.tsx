'use client';

import {useTranslations} from '../i18n/LanguageProvider';
import { PRODUCT_NAME } from '../utils/brand';

/** The same accessible name and spelling in the header, dashboard and footer. */
export function ProductWordmark() {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [name, suffix] = PRODUCT_NAME.split('.');
  return <span data-product-brand>{i18nNode(name)}<span className="text-togg-turquoise">.{i18nNode(suffix)}</span></span>;
}
