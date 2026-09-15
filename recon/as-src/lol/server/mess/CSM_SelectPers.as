class lol.server.mess.CSM_SelectPers extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SelectPers(num)
   {
      super();
      this._name = "selPers";
      this.addProp("num",num);
   }
}
