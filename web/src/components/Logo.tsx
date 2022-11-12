import * as React from "react";

interface LogoProps {
  className: string;
}

export const Logo: React.FC<LogoProps> = ({ className }) => {
  return (
    <svg
      width="296"
      height="53"
      viewBox="0 0 296 53"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M34.6953 52V0.8125H24.9219V21.8008H10.4375V0.8125H0.628906V52H10.4375V29.8164H24.9219V52H34.6953ZM46.332 0.8125V8.79297H56.0703V44.0547H46.332V52H75.9336V44.0547H65.9492V8.79297H75.9336V0.8125H46.332ZM125.012 8.86328V0.8125H83.7383V8.86328H99.3125V52H109.227V8.86328H125.012Z"
        fill="black"
      />
      <path
        d="M157.215 38.6406C157.215 39.5547 157.027 40.3984 156.652 41.1719C156.277 41.9219 155.738 42.5664 155.035 43.1055C154.332 43.6445 153.465 44.0664 152.434 44.3711C151.426 44.6758 150.266 44.8281 148.953 44.8281C147.477 44.8281 146.117 44.6641 144.875 44.3359C143.656 44.0078 142.613 43.4922 141.746 42.7891C140.855 42.0859 140.164 41.1836 139.672 40.082C139.18 38.9805 138.91 37.6562 138.863 36.1094H129.16C129.16 38.7578 129.664 41.0664 130.672 43.0352C131.703 45.0039 133.098 46.7148 134.855 48.168C136.707 49.6445 138.875 50.7695 141.359 51.543C143.867 52.293 146.398 52.668 148.953 52.668C151.555 52.668 153.957 52.3633 156.16 51.7539C158.363 51.1211 160.262 50.1953 161.855 48.9766C163.449 47.7812 164.691 46.3164 165.582 44.582C166.496 42.8242 166.953 40.8203 166.953 38.5703C166.953 35.9688 166.355 33.6719 165.16 31.6797C163.965 29.6875 162.359 27.9414 160.344 26.4414C159.008 25.5273 157.543 24.7188 155.949 24.0156C154.355 23.3125 152.68 22.7148 150.922 22.2227C149.281 21.7773 147.805 21.2969 146.492 20.7812C145.203 20.2656 144.102 19.6914 143.188 19.0586C142.273 18.4492 141.57 17.7578 141.078 16.9844C140.609 16.2109 140.375 15.3438 140.375 14.3828C140.375 13.4688 140.551 12.625 140.902 11.8516C141.277 11.0547 141.816 10.3633 142.52 9.77734C143.223 9.21484 144.078 8.78125 145.086 8.47656C146.117 8.14844 147.289 7.98438 148.602 7.98438C150.031 7.98438 151.273 8.18359 152.328 8.58203C153.406 8.95703 154.309 9.48438 155.035 10.1641C155.738 10.8672 156.266 11.6992 156.617 12.6602C156.992 13.6211 157.203 14.6758 157.25 15.8242H166.883C166.883 13.5273 166.438 11.418 165.547 9.49609C164.656 7.57422 163.414 5.91016 161.82 4.50391C160.227 3.12109 158.316 2.04297 156.09 1.26953C153.887 0.496094 151.449 0.109375 148.777 0.109375C146.199 0.109375 143.809 0.449219 141.605 1.12891C139.402 1.78516 137.492 2.73438 135.875 3.97656C134.258 5.21875 132.992 6.71875 132.078 8.47656C131.164 10.2344 130.707 12.1914 130.707 14.3477C130.707 16.2227 131.047 17.957 131.727 19.5508C132.43 21.1445 133.461 22.5977 134.82 23.9102C136.18 25.2227 137.926 26.4297 140.059 27.5312C142.215 28.6328 144.711 29.5703 147.547 30.3438C149.375 30.8359 150.898 31.375 152.117 31.9609C153.359 32.5234 154.367 33.1445 155.141 33.8242C155.891 34.5273 156.418 35.2773 156.723 36.0742C157.051 36.8711 157.215 37.7266 157.215 38.6406ZM199.051 41.3125L202.039 52H212.445L195.992 0.8125H187.027L170.258 52H180.664L183.688 41.3125H199.051ZM186.113 32.9102L191.492 14.0664L196.73 32.9102H186.113ZM229.074 52H239.129L254.633 0.8125H243.734L235.016 34.2109L234.066 37.6914L233.188 34.2461L224.504 0.8125H213.605L229.074 52ZM291.863 29.5703V21.7656H270.84V8.86328H295.309V0.8125H260.926V52H295.414V44.0195H270.84V29.5703H291.863Z"
        fill="#CC6666"
      />
    </svg>
  );
};
