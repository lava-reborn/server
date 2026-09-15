class lol.server.mess.CSM_BA_ConvertAfroToGold extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_BA_ConvertAfroToGold(gold)
   {
      super();
      this._name = "c_ga";
      this.addProp("gold",gold);
   }
}
