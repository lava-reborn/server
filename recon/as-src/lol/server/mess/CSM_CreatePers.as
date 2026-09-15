class lol.server.mess.CSM_CreatePers extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_CreatePers(name, sex, res)
   {
      super();
      this._name = "newPers";
      this.addProp("res",res);
      this.addProp("sex",sex);
      this.addProp("name",name);
   }
}
