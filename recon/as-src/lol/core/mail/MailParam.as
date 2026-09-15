class lol.core.mail.MailParam
{
   var clanLetter_express;
   var clanLetter_usual;
   var delivery_express;
   var delivery_usual;
   var itemKg_express;
   var itemKg_usual;
   var tradeLetter_express;
   var tradeLetter_usual;
   function MailParam(_data, _time)
   {
      this.tradeLetter_usual = [_data[0],Number(_time[0] / 60)];
      this.tradeLetter_express = [Number(_data[1] / 100),Number(_time[1] / 60)];
      this.clanLetter_usual = [_data[2],Number(_time[2] / 60)];
      this.clanLetter_express = [Number(_data[3] / 100),Number(_time[3] / 60)];
      this.itemKg_usual = [_data[4],Number(_time[4] / 60)];
      this.itemKg_express = [Number(_data[5] / 100),Number(_time[5] / 60)];
      this.delivery_usual = [_data[6],Number(_time[6] / 60)];
      this.delivery_express = [Number(_data[7] / 100),Number(_time[7] / 60)];
   }
}
