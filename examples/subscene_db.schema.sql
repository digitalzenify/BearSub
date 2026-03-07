CREATE TABLE all_subs (
  id int(11) NOT NULL,
  title varchar(255) DEFAULT NULL,
  imdb int(10) UNSIGNED DEFAULT NULL,
  date datetime DEFAULT NULL,
  author_name varchar(255) DEFAULT NULL,
  author_id int(11) DEFAULT NULL,
  lang varchar(255) DEFAULT NULL,
  comment varchar(255) DEFAULT NULL,
  releases text DEFAULT NULL,
  subscene_link varchar(255) DEFAULT NULL,
  fileLink varchar(255) DEFAULT NULL
);
