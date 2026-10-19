import { PRODUCT_NAME } from '../utils/brand';

/** The same accessible name and spelling in the header, dashboard and footer. */
export function ProductWordmark() {
  const [name, suffix] = PRODUCT_NAME.split('.');
  return <span data-product-brand>{name}<span className="text-togg-turquoise">.{suffix}</span></span>;
}
