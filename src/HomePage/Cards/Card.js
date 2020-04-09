// @flow
import { Card, Typography } from "@material-ui/core";
import Avatar from "@material-ui/core/Avatar";
import CardActions from "@material-ui/core/CardActions";
import CardContent from "@material-ui/core/CardContent";
import CardHeader from "@material-ui/core/CardHeader";
import IconButton from "@material-ui/core/IconButton";
import FavoriteIcon from "@material-ui/icons/Favorite";
import ShareIcon from "@material-ui/icons/Share";
import React from "react";
import type { Node } from "react";

type Props = {
  Icon: Node,
  title: string,
  subheader?: string,
  content: string,
  actions: string
};

export default function MainCard(props: Props) {
  const { Icon, title, subheader, content, actions } = props;
  return (
    <Card>
      <CardHeader
        avatar={Icon}
        title={title}
        subheader={subheader}
      ></CardHeader>

      <CardContent>
        <Typography variant="body2" color="textSecondary" component="p">
          {content}
        </Typography>
      </CardContent>
      <CardActions>
        {actions}
        {/* <IconButton aria-label="add to favorites">
          <FavoriteIcon />
        </IconButton>
        <IconButton aria-label="share">
          <ShareIcon />
        </IconButton> */}
      </CardActions>
    </Card>
  );
}
