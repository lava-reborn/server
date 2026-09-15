class lol.server.mess.CSM_SSUpdate extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSUpdate(s_status, obj, param)
   {
      super();
      this._name = "ss_upd";
      this.addProp("param",param);
      this.addProp("obj",obj);
      this.addProp("s_status",s_status);
   }
}
