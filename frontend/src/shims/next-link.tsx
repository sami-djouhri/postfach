import { Link as RouterLink, LinkProps as RouterLinkProps } from 'react-router-dom';
import { ReactNode, forwardRef, AnchorHTMLAttributes } from 'react';

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & {
  href: string;
  children?: ReactNode;
  prefetch?: boolean;
  scroll?: boolean;
  replace?: boolean;
} & Partial<Pick<RouterLinkProps, 'state'>>;

const NextLinkShim = forwardRef<HTMLAnchorElement, Props>(function NextLinkShim(
  { href, children, prefetch: _p, scroll: _s, replace, state, ...rest },
  ref,
) {
  if (/^(https?:|mailto:|tel:|#)/.test(href)) {
    return (
      <a ref={ref} href={href} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <RouterLink ref={ref as any} to={href} replace={replace} state={state} {...(rest as any)}>
      {children}
    </RouterLink>
  );
});

export default NextLinkShim;
