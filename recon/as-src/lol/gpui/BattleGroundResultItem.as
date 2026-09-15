class lol.gpui.BattleGroundResultItem extends lol.gpui.GPUIObject
{
   var deaths_txt;
   var kills_txt;
   var name_txt;
   var tf;
   function BattleGroundResultItem()
   {
      super();
      this.tf = new TextFormat();
   }
   function init(name, kills, deaths, Team, OwnPlayer)
   {
      this.tf.bold = OwnPlayer;
      this.tf.color = Team != 0 ? 65280 : 16711680;
      trace("Team == " + Team + ", tf.color = " + this.tf.color);
      this.name_txt.text = name;
      this.name_txt.setTextFormat(this.tf);
      this.kills_txt.text = String(kills);
      this.kills_txt.setTextFormat(this.tf);
      this.deaths_txt.text = String(deaths);
      this.deaths_txt.setTextFormat(this.tf);
   }
}
